# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _

class PurchaseApprovalLevel(models.Model):
    _name = "purchase.approval.level"
    _description = "Purchase Approval Level"

    name = fields.Char("Name")
    sequence = fields.Integer("Sequence", copy=False)
