# -*- coding: utf-8 -*-
##############################################################################
#
#    Author: Steve Ferry
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
import datetime
import time
import logging

from openerp import fields, _

from .base_parser import BaseSwissParser

_logger = logging.getLogger(__name__)


class G11Parser(BaseSwissParser):
    """
    Parser for BVR DD type 2 Postfinance Statements
    (can be wrapped in a g11 file)
    """

    _ftype = 'g11'

    def __init__(self, data_file):
        """Constructor
        Splitting data_file in lines
        """

        super(G11Parser, self).__init__(data_file)
        self.lines = data_file.splitlines()
        self.reject_reason = {
            '01': _("Insufficient cover funds."),
            '02': _("Debtor protestation."),
            '03': _("Debtor’s account number and address do not match."),
            '04': _("Postal account closed."),
            '05': _("Postal account blocked/frozen."),
            '06': _("Postal account holder deceased."),
            '07': _("Postal account number non-existent.")
        }

    def ftype(self):
        """Gives the type of file we want to import

        :return: imported file type
        :rtype: string
        """

        return super(G11Parser, self).ftype()

    def get_currency(self):
        """Returns the ISO currency code of the parsed file

        :return: The ISO currency code of the parsed file eg: CHF
        :rtype: string
        """

        return super(G11Parser, self).get_currency()

    def get_account_number(self):
        """Return the account_number related to parsed file

        :return: The account number of the parsed file
        :rtype: string
        """

        return super(G11Parser, self).get_account_number()

    def get_statements(self):
        """Return the list of bank statement dict.
         Bank statements data: list of dict containing
            (optional items marked by o) :
            - 'name': string (e.g: '000000123')
            - 'date': date (e.g: 2013-06-26)
            -o 'balance_start': float (e.g: 8368.56)
            -o 'balance_end_real': float (e.g: 8888.88)
            - 'transactions': list of dict containing :
                - 'name': string
                   (e.g: 'KBC-INVESTERINGSKREDIET 787-5562831-01')
                - 'date': date
                - 'amount': float
                - 'unique_import_id': string
                -o 'account_number': string
                    Will be used to find/create the res.partner.bank in odoo
                -o 'note': string
                -o 'partner_name': string
                -o 'ref': string

        :return: a list of statement
        :rtype: list
        """

        return super(G11Parser, self).get_statements()

    def file_is_known(self):
        """Predicate the tells if the parser can parse the data file

        :return: True if file is supported
        :rtype: bool
        """

        return self.lines[-1][0:3] == '097'

    def _parse_currency_code(self):
        """Parse file currency ISO code

        :return: the currency ISO code of the file eg: CHF
        :rtype: string
        """

        return self.lines[-1][128:131]

    def _parse_statement_balance_end(self):
        """Parse file start and end balance

        :return: the file end balance
        :rtype: float
        """

        total_line = self.lines[-1]
        return ((float(total_line[45:57]) / 100) -
                (float(total_line[101:113]) / 100))

    def _parse_transactions(self):
        """Parse bank statement lines from file
        list of dict containing :
            - 'name': string (e.g: 'KBC-INVESTERINGSKREDIET 787-5562831-01')
            - 'date': date
            - 'amount': float
            - 'unique_import_id': string
            -o 'account_number': string
                Will be used to find/create the res.partner.bank in odoo
            -o 'note': string
            -o 'partner_name': string
            -o 'ref': string

        :return: a list of transactions
        :rtype: list
        """

        transactions = []
        for line in self.lines:
            if line[0:3] != '097':
                ref = line[15:42]
                currency = line[42:45]
                amount = float(line[45:57]) / 100
                transaction_date = time.strftime(
                    '%Y-%m-%d', time.strptime(line[108:116], '%Y%m%d'))
                # commission = float(line[141:147]) / 100
                note = ''

                if line[0:3] == '084':
                    # Fail / Debit record
                    reject_code = line[128:130]
                    if reject_code == '02':
                        # Debit record
                        amount *= -1
                        note = self.reject_reason[reject_code]
                    else:
                        # Failed transactions. Get the error reason and
                        # put it on the OBI field.
                        note = self.reject_reason[
                            reject_code] + '\n' + _(
                                "Amount to debit was %s %f") % (
                                    currency, amount)
                        amount = 0.0

                # Add information to OBI if the transaction is a test.
                if line[5] == '3':
                    note = _("-- Test transaction --") + '\n' + note

                transactions.append({
                    'name': '/',
                    'ref': ref,
                    'unique_import_id': ref,
                    'amount': amount,
                    'date': transaction_date,
                    'note': note,
                })
        return transactions

    def validate(self):
        """Validate the bank statement
        :param total_line: Last line in the g11 file. Beginning with '097'
        :return: Boolean
        """

        total_line = self.lines[-1]
        transactions = 0
        transactions += int(
            total_line[57:69]) + int(
                total_line[89:101]) + int(
                    total_line[113:125])
        return (len(self.statements[0]['transactions']) == transactions)

    def _parse_statement_date(self):
        """Parse file statement date
        :return: A date usable by Odoo in write or create dict
        """

        date = datetime.date.today()
        return fields.Date.to_string(date)

    def _parse(self):
        """
        Launch the parsing through The g11 file.
        """

        self.currency_code = self._parse_currency_code()
        statement = {}
        statement['balance_start'] = 0.0
        statement['balance_end_real'] = self._parse_statement_balance_end()
        statement['date'] = self._parse_statement_date()
        statement['attachments'] = []
        statement['transactions'] = self._parse_transactions()
        self.statements.append(statement)
        return self.validate()
