# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _

class PurchaseAdditionalDetails(models.Model):
    _name = "purchase.additional.details"
    _description = "Purchase Additional Details"
    
    purchase_id = fields.Many2one("purchase.order",
                                 string="Purchase Order")
    purchase_line_id = fields.Many2one('purchase.order.line',string="Purchase Order Line")
    description = fields.Char(string="Description")
    details = fields.Char(string="Details",copy=True)
    company_id = fields.Many2one('res.company',string="Company")
                 
    product_id = fields.Many2one("product.product",
                                 string="Product")
    quantity = fields.Float(string="Qty")
    for_staff = fields.Char(string="Staff name/Team",copy=True)
    position = fields.Char(string="Position",copy=True)
    location = fields.Char(string="Location",copy=True)
    warranty = fields.Char(string="Warranty/Refund Terms",copy=True)
    remark = fields.Char(string="Remarks",copy=True)
