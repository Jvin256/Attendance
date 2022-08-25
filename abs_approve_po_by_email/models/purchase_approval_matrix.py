# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _

class PurchaseApprovalMatrix(models.Model):
    _name = "purchase.approval.matrix"
    _description = "Purchase Approval Matrix"

    name = fields.Char("Name")
    company_id = fields.Many2one("res.company",
                             string="Company")
    matrix_line_ids = fields.One2many("purchase.approval.matrix.line",
                                      "matrix_id",
                                     string="Matrix Line")
             
