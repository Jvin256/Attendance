# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _,Command
from odoo.tools.misc import formatLang, get_lang
from odoo.exceptions import AccessError, UserError, ValidationError
from werkzeug.urls import url_encode
import json
import uuid
from datetime import datetime
import logging
_logger = logging.getLogger(__name__)

class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    @api.model
    def create(self, vals):
        if not vals['purchase_additional_details_ids']:
            purchase_additional_details_ids = []
            for line in vals['order_line']:
                for i in range(int(line[2]['product_qty'])):
                    additional_vals = {'product_id': line[2]['product_id'], 'quantity': 1,
                                       'company_id': vals['company_id']}
                    purchase_additional_details_ids.append(Command.create(additional_vals))
            vals['purchase_additional_details_ids'] = purchase_additional_details_ids
        res = super(PurchaseOrder, self).create(vals)
        return res

    @api.model
    def _default_access_token(self):
        return uuid.uuid4().hex

    purpose = fields.Char("Purpose")
    justification = fields.Char("EC Justification")
    req_justification = fields.Char("Requestor Justification")
    access_token = fields.Char('Security Token', copy=False, default=_default_access_token)
    purchase_approval_history_ids = fields.One2many("purchase.approval.history", "purchase_order_id", string="Purchase Approval History")
    purchase_additional_details_ids = fields.One2many("purchase.additional.details",
                                                    "purchase_id",
                                                    string="Purchase Additional Details",copy=True)
    level_id = fields.Many2one("purchase.approval.level",
                              string="To Approve", copy=False)
    cc_user_id = fields.Many2one('res.partner',string="CC to")
    ecpic =fields.Many2one('res.users',string="EC PIC",strore=True)
    amount_in_usd = fields.Float(string="Total (USD)")

    @api.depends('order_line.taxes_id', 'order_line.price_subtotal', 'amount_total', 'amount_untaxed')
    def _compute_tax_totals_json(self):
        def compute_taxes(order_line):
            return order_line.taxes_id._origin.compute_all(**order_line._prepare_compute_all_values())

        account_move = self.env['account.move']
        for order in self:
            tax_lines_data = account_move._prepare_tax_lines_data_for_totals_from_object(order.order_line,
                                                                                         compute_taxes)
            tax_totals = account_move._get_tax_totals(order.partner_id, tax_lines_data, order.amount_total,
                                                      order.amount_untaxed, order.currency_id)
            order.tax_totals_json = json.dumps(tax_totals)
            currency_id_usd = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
            if currency_id_usd and order.currency_id:
                amount_usd = order.currency_id._convert(tax_totals['amount_total'], currency_id_usd, order.company_id, order.date_order)
                order.amount_in_usd = amount_usd

    @api.onchange('justification')
    def onchange_justification_req(self):
        self.ecpic = self.env.user.id

    def button_confirm(self):
        res =  super(PurchaseOrder, self).button_confirm()
        if not self.user_has_groups('purchase.group_purchase_manager'):
            self.get_matrix_id()
        return res

    def button_approve(self, force=False):
        #self = self.filtered(lambda order: order._approval_allowed())
        ### START ###
        po_obj = self.filtered(lambda order: order._approval_allowed())
        if not po_obj:
            po_obj = self
        self = po_obj 
        ### STOP ###
        self.write({'state': 'purchase', 'date_approve': fields.Datetime.now()})
        self.filtered(lambda p: p.company_id.po_lock == 'lock').write({'state': 'done'})
        return {}

    def get_matrix_id(self):
        matrix_obj = self.env["purchase.approval.matrix"].sudo()
        if self.company_id:
            matrix_id = matrix_obj.search([("company_id", "=", self.company_id.id)],limit=1)
            if not self.purchase_approval_history_ids and matrix_id and matrix_id.matrix_line_ids:
                line_ids = matrix_id.matrix_line_ids
                line_list = []
                for line in line_ids:
                    if line.amount <= self.amount_total and line.level_id.sequence == 1:
                        line_list.append(line)
                if line_list:
                    self.write({"level_id":line_list[-1].level_id.id})
                    self.asked_for_approval(line_list[-1],level_1=True)

            elif self.purchase_approval_history_ids and matrix_id and matrix_id.matrix_line_ids:
                last_history_id = self.purchase_approval_history_ids[-1]
                line_ids = matrix_id.matrix_line_ids
                line_list = []
                for line in line_ids:
                    if line.amount <= self.amount_total and line.level_id.sequence == last_history_id.level_id.sequence + 1:
                        line_list.append(line)
                if line_list:
                    self.asked_for_approval(line_list[-1],level_1=False)
                    self.write({"level_id":line_list[-1].level_id.id})
                else:
                    self.write({"level_id":False})
                    self.sudo().button_approve()

    def send_mail_to_approver(self,line_id,last_history_id,approved):
        template = self.env.ref('abs_approve_po_by_email.receive_email_template')
        if template and last_history_id:
            assert template._name == 'mail.template'
            body_html = ''
            if approved:
                body_html = self.get_receive_body_html(body_html,line_id,last_history_id)
            elif not approved:
                body_html = self.get_reject_body_html(body_html,line_id,last_history_id)
            subject = 'Ref {0}'.format(self.name)
            template.update({"partner_to":last_history_id.user_id.partner_id.id,
                             "body_html":body_html,
                             "email_from":self.user_id.email,"subject":subject})
            mail_create = self.env['mail.template'].browse(template.id).sudo().send_mail(self.id)
            if mail_create:
                mail = self.env['mail.mail'].browse(mail_create).sudo().send()

    def get_receive_body_html(self,body_html,line_id,last_history_id):
        body_html += '<div style="margin: 0px; padding: 0px;">\
                          <p style="margin: 0px; padding: 0px; font-size: 13px;">\
                          Hello {0},<br/><br/>\
                          {1} has approved the {2}.\
                          <br/><br/>Best regards, <br/> \
                          {3}</p></div>'.format(last_history_id.user_id.name,
                          line_id.user_id.name,self.name,
                          self.env.user.signature)
        return body_html

    def get_reject_body_html(self,body_html,line_id,last_history_id):
        body_html += '<div style="margin: 0px; padding: 0px;">\
                          <p style="margin: 0px; padding: 0px; font-size: 13px;">\
                          Hello {0},<br/><br/>\
                          {1} has rejected the {2}.\
                          <br/><br/>Best regards, <br/> \
                          {3}</p></div>'.format(last_history_id.user_id.name,
                          line_id.user_id.name,self.name,
                          self.env.user.signature)
        return body_html

    def send_mail_to_requestor(self,line_id,last_history_id,approved):
        template = self.env.ref('abs_approve_po_by_email.receive_email_template')
        if template and last_history_id:
            assert template._name == 'mail.template'
            body_html = ''
            if approved:
                body_html = self.get_receive_requestor_body_html(body_html,line_id,last_history_id)
            elif not approved:
                body_html = self.get_reject_requestor_body_html(body_html,line_id,last_history_id)
            subject = 'Ref {0}'.format(self.name)
            template.update({"partner_to":self.user_id.partner_id.id,
                             "body_html":body_html,
                             "email_from":line_id.user_id.email,"subject":subject})
            mail_create = self.env['mail.template'].browse(template.id).sudo().send_mail(self.id)
            if mail_create:
                mail = self.env['mail.mail'].browse(mail_create).sudo().send()

    def get_receive_requestor_body_html(self,body_html,line_id,last_history_id):
        body_html += '<div style="margin: 0px; padding: 0px;">\
                          <p style="margin: 0px; padding: 0px; font-size: 13px;">\
                          Hello {0},<br/><br/>\
                          {1} has approved the {2}.\
                          <br/><br/>Best regards, <br/> \
                          {3}</p></div>'.format(self.user_id.name,
                          line_id.user_id.name,self.name,
                          self.env.user.signature)
        return body_html

    def get_reject_requestor_body_html(self,body_html,line_id,last_history_id):
        body_html += '<div style="margin: 0px; padding: 0px;">\
                          <p style="margin: 0px; padding: 0px; font-size: 13px;">\
                          Hello {0},<br/><br/>\
                          {1} has rejected the {2}.\
                          <br/><br/>Best regards, <br/> \
                          {3}</p></div>'.format(self.user_id.name,
                          line_id.user_id.name,self.name,
                          self.env.user.signature)
        return body_html

    def asked_for_approval(self,line_id,level_1):
        template = self.env.ref('abs_approve_po_by_email.email_template_pr_approval')
        if template:
            assert template._name == 'mail.template'
            body_html = ''
            body_html = self.get_body_html(body_html,line_id,level_1)
            subject = 'Ref {0}'.format(self.name)
            if self.cc_user_id and self.cc_user_id.email:
                cc_mail = self.cc_user_id.email
            else:
                cc_mail = ''
            template.update({'partner_to':line_id.user_id.partner_id.id,"body_html":body_html,"email_from":self.user_id.email,"subject":subject,"email_cc":cc_mail},)
            mail_create = self.env['mail.template'].browse(template.id).sudo().send_mail(self.id)
            if mail_create:
                mail = self.env['mail.mail'].browse(mail_create).sudo().send()

    def create_history_for_approved(self,matrix_line,po_id):
        matrix_line_obj = self.env["purchase.approval.matrix.line"].sudo()
        purchase_approval_history_obj = self.env["purchase.approval.history"].sudo()
        if self.env.context.get("from_website"):
            if matrix_line:
                matrix_line_id = matrix_line_obj.browse(int(matrix_line))
                purchase_approval_history_dict = {} 
                if matrix_line_id:
                    purchase_approval_history_dict = {
                                                      "purchase_order_id":int(po_id),
                                                      "level_id":matrix_line_id.level_id.id,
                                                      "user_id":matrix_line_id.user_id.id,
                                                      "status_approval":"approved",
                                                      "approval_history_datetime":datetime.now()
                                                     }   
                    purchase_approval_history_obj.create(purchase_approval_history_dict)
                    if len(self.purchase_approval_history_ids) >= 2:
                        last_history_id = self.purchase_approval_history_ids[-2]
                        self.send_mail_to_approver(matrix_line_id,last_history_id,approved=True)
                        self.send_mail_to_requestor(matrix_line_id,last_history_id,approved=True)

    def create_history_for_rejected(self,matrix_line,po_id):
        matrix_line_obj = self.env["purchase.approval.matrix.line"].sudo()
        purchase_approval_history_obj = self.env["purchase.approval.history"].sudo()
        if self.env.context.get("from_website"):
            if matrix_line:
                matrix_line_id = matrix_line_obj.browse(int(matrix_line))
                purchase_approval_history_dict = {} 
                if matrix_line_id:
                    purchase_approval_history_dict = {
                                                      "purchase_order_id":int(po_id),
                                                      "level_id":matrix_line_id.level_id.id,
                                                      "user_id":matrix_line_id.user_id.id,
                                                      "status_approval":"rejected",
                                                      "approval_history_datetime":datetime.now()
                                                     }   
                    purchase_approval_history_obj.create(purchase_approval_history_dict)
                    order_id = self.browse(int(po_id))
                    order_id.write({"level_id":False})
                    order_id.button_cancel()
                    if len(self.purchase_approval_history_ids) >= 2:
                        last_history_id = self.purchase_approval_history_ids[-2]
                        order_id.send_mail_to_approver(matrix_line_id,last_history_id,approved=False)
                        order_id.send_mail_to_requestor(matrix_line_id,last_history_id,approved=False)

    def get_body_html(self,body_html,line_id,level_1):
        """Code for getting the body html"""
        if self.state == 'to approve':
            body_html += '<div style="margin: 0px; padding: 0px;">\
                                      <p style="margin: 0px; padding: 0px; font-size: 13px;">\
                                      Hello {0},<br/><br/>\
                                       This PO is waiting for your approval.\
                                      <br/>'.format(line_id.user_id.name)
        else:
            body_html += '<div style="margin: 0px; padding: 0px;">\
                              <p style="margin: 0px; padding: 0px; font-size: 13px;">\
                              Hello {0},<br/><br/>\
                              {1} is asking for approval of this order.\
                              <br/>'.format(line_id.user_id.name,
                              self.user_id.name)
        if not level_1:
            body_html += "<br/>The purchase order has been approved by Expense control.<br/>"

        body_html += "<br/> <b>Company : </b>{0}<br/>\
                             <b>Vendor : </b>{1}<br/>\
                             <b>Amount in USD : </b>USD {2}<br/>\
                             <b>Purpose : </b>{3}<br/> \
                             <b>Requestor Justification : </b>{4}<br/> \
                             <b>Requestor : </b>{5}<br/> \
                             <b>EC Justification : </b>{6}<br/> \
                             <b>EC PIC : </b>{7}<br/>".format(self.company_id.name,
                                                          self.partner_id.name,
                                                          self.amount_in_usd,
                                                          self.purpose,
                                                          self.req_justification if self.req_justification else '',
                                                          self.user_id.name,
                                                          self.justification if self.justification else '',
                                                          self.ecpic.name if self.ecpic else '')
        if self.order_line:
            line_content = ""
            total_amount = 0.0
            for line in self.order_line:
                total_amount += line.price_subtotal
                line_content += "<tr>\
                                     <td>{0}</td>\
                                     <td>{1}</td>\
                                     <td>{2}</td>\
                                     <td>{3}</td>\
                                     <td>{4}</td>\
                                 </tr>".format(line.product_id.name,
                                               line.product_qty,
                                               self.currency_id.name,
                                               line.price_unit,
                                               line.price_subtotal)
            
            body_html += "<br/><br/><b>Purchase Request : </b> \
                                     <table style='width:60%; border-collapse: collapse;' border='1px solid black'>\
                                         <tr>\
                                             <th>Product</th>\
                                             <th>Quantity</th>\
                                             <th>Currency</th>\
                                             <th>Unit Price</th>\
                                             <th>Sub Total</th>\
                                         </tr>\
                                         <tbody>{0}</tbody>\
                                         <tr>\
                                            <th style='border-right-style:hidden;\
                                                       border-left-style:hidden;\
                                                       border-bottom-style:hidden;'></th>\
                                            <th style='border-bottom-style:hidden;'></th>\
                                            <th>TOTAL</th>\
                                            <td>{1}</td>\
                                         </tr>\
                                     </table>".format(line_content,total_amount or '')

        if self.purchase_additional_details_ids:
            additional_content = ""
            for details_id in self.purchase_additional_details_ids:
                additional_content += "<tr>\
                                     <td>{0}</td>\
                                     <td>{1}</td>\
                                     <td>{2}</td>\
                                     <td>{3}</td>\
                                     <td>{4}</td>\
                                     <td>{5}</td>\
                                     <td>{6}</td>\
                                     <td>{7}</td>\
                                     <td>{8}</td>\
                                 </tr>".format(details_id.product_id.name or '',
                                               details_id.quantity or '',
                                               details_id.company_id.name or '',
                                               details_id.location or '',
                                               details_id.details or '',
                                               details_id.for_staff or '',
                                               details_id.position or '',
                                               details_id.warranty or '',
                                               details_id.remark or '',
                                               )
            body_html += "<br/><br/><b>Additional Details : </b>\
                                     <table style='width:60%; border-collapse: collapse;' border='1px solid black'>\
                                         <tr>\
                                             <th>Product</th>\
                                             <th>Qty</th>\
                                             <th>Company</th>\
                                             <th>Location</th>\
                                             <th>Details</th>\
                                             <th>Staff name/Team</th>\
                                             <th>Position</th>\
                                             <th>Warranty/Refund Terms</th>\
                                             <th>Remarks</th>\
                                         </tr>\
                                         <tbody>{0}</tbody>\
                                     </table>\
                                     <br/>".format(additional_content)
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        if base_url and self.id:
            body_html += '<br/> Purchase Order No: <a href="{0}/web#id={1}&view_type=form&model={2}">\
                {3}</a>'.format(base_url,self.id,'purchase.order',self.name)
        body_html += '<br/>You can  Approve or Reject the purchase order from the following button.\
                      <br/><br/>\
            <a href="/purchase/approval?token={0}&amp;id={1}&amp;matrix_id={2}"\
            style="padding: 5px 10px; color: #FFFFFF; text-decoration: none; background-color: green; border: 1px solid #875A7B; border-radius: 3px">\
            Approve</a>'.format(self.access_token,self.id,line_id.id)

        body_html += '&nbsp;&nbsp;<a href="/purchase/reject?token={0}&amp;id={1}&amp;matrix_id={2}"\
            style="padding: 5px 10px; color: #FFFFFF; text-decoration: none; background-color: #875A7B; border: 1px solid #875A7B; border-radius: 3px">\
            Reject</a><br/><br/>\
                      <br/>Best regards, <br/> {3}</p></div>'.format(self.access_token,self.id,line_id.id,self.env.user.signature)
        return body_html

    def button_draft(self):
        res = super(PurchaseOrder, self).button_draft()
        self.sudo().write({"level_id":False})
        if self.purchase_approval_history_ids:
            self.purchase_approval_history_ids.sudo().unlink()
        return res
class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def CreatePurchaseAdditionalLine(self):
        for record in self:
            lines = record.order_id.purchase_additional_details_ids.filtered(lambda line: line.product_id.id ==  record.product_id.id)
            exist_lines = len(lines)
            prod_range = int(record.product_qty) - exist_lines
            if prod_range > 0:
                for i in range(int(prod_range)):
                    vals = {'product_id':record.product_id.id,'quantity':1,'company_id':record.order_id.company_id.id,'purchase_line_id':record.id,'purchase_id':record.order_id.id}
                    additional_create = self.env['purchase.additional.details'].create(vals)
            elif prod_range < 0:
                remove_lines = lines[prod_range:]
                remove_lines.unlink()
            else:
                pass


