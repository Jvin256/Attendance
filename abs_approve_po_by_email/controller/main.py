# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.http import request, Response
from odoo.tools.translate import _
from odoo.addons.portal.controllers.portal import pager as portal_pager, CustomerPortal
import werkzeug

class POApproval(CustomerPortal):

    @http.route(['/purchase/approval'], type='http', auth="public")
    def button_approval(self, token, id, matrix_id, **kwargs):
        po_id = request.env['purchase.order'].sudo().search([("access_token", "=", token), ("id", "=", id)])
        matrix_line_id = request.env['purchase.approval.matrix.line'].sudo().search([("id", "=", matrix_id)])
        if po_id.state == 'to approve' and matrix_line_id and po_id.level_id == matrix_line_id.level_id:
            po_id.sudo().with_context(from_website=True).create_history_for_approved(matrix_id,po_id)
            po_id.get_matrix_id()
            return werkzeug.utils.redirect('/order_confirmed')
        else:
            return werkzeug.utils.redirect('/order_block')

    @http.route(['/purchase/reject'], type='http', auth="public")
    def button_reject(self, token, id, matrix_id, **kwargs):
        # import pdb;pdb.set_trace();
        po_id = request.env['purchase.order'].sudo().search([("access_token", "=", token), ("id", "=", id)])
        matrix_line_id = request.env['purchase.approval.matrix.line'].sudo().search([("id", "=", matrix_id)])
        if po_id.state == 'to approve' and matrix_line_id and po_id.level_id == matrix_line_id.level_id:
            po_id.sudo().with_context(from_website=True).create_history_for_rejected(matrix_id,po_id)
            return werkzeug.utils.redirect('/order_rejected')
        else:
            return werkzeug.utils.redirect('/order_block')
