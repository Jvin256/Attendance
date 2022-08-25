# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _

class PurchaseApprovalMatrixLine(models.Model):
    _name = "purchase.approval.matrix.line"
    _description = "Purchase Approval Matrix Line"

    amount = fields.Float("Amount")
    level_id = fields.Many2one("purchase.approval.level",
                              string="Level")
    user_id = fields.Many2one("res.users",
                             string="Approver")
    matrix_id = fields.Many2one("purchase.approval.matrix",
                             string="Matrix")

