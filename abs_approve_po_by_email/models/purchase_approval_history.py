# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _

class PurchaseApprovalHistory(models.Model):
    _name = "purchase.approval.history"
    _description = "Purchase Approval History"

    status_approval = fields.Selection([("approved","Approved"),
                                        ("rejected","Rejected")],
                                        string="Status",
                                        copy=False)
    approval_history_datetime = fields.Datetime("Date")
    level_id = fields.Many2one("purchase.approval.level",
                              string="Level")
    purchase_order_id = fields.Many2one("purchase.order",
                                       string="Purchase Order")
    user_id = fields.Many2one("res.users",
                             string="Approver")
