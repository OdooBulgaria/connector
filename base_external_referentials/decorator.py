# -*- encoding: utf-8 -*-
###############################################################################
#                                                                             #
#   base_external_referentials for OpenERP                                    #
#   Copyright (C) 2011 Akretion Sébastien BEAU <sebastien.beau@akretion.com>  #
#                                                                             #
#   This program is free software: you can redistribute it and/or modify      #
#   it under the terms of the GNU Affero General Public License as            #
#   published by the Free Software Foundation, either version 3 of the        #
#   License, or (at your option) any later version.                           #
#                                                                             #
#   This program is distributed in the hope that it will be useful,           #
#   but WITHOUT ANY WARRANTY; without even the implied warranty of            #
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the             #
#   GNU Affero General Public License for more details.                       #
#                                                                             #
#   You should have received a copy of the GNU Affero General Public License  #
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.     #
#                                                                             #
###############################################################################

from osv import osv
import pooler
from tools.translate import _
from message_error import MappingError
import functools

def only_for_referential(referential_type_filter):
    """ 
    This decorator will execute the code of the function decorated only if
    the referential_type match with the referential_type pass in the context
    If not super method will be call.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapped(self, cr, uid, argument, *args, **kwargs):
            if self._name == 'external.referential' and (isinstance(argument, list) or isinstance(argument, int)):
                referential_id = isinstance(argument, list) and argument[0] or argument
                referential = self.browse(cr, uid, referential_id)
            else:
                referential = argument.referential_id
            if referential.type_id.name.lower() == referential_type_filter.lower():
                return func(self, cr, uid, argument, *args, **kwargs)
            else:
                # TODO REFACTOR this code
                # It's the first time I do something like that :S
                # I never use decorator before :(
                # My aim is to call the super method instead of original method
                # when the referential is not the appropriated referential
                # Can you check my code I share your experience about this kind of feature?
                # Can you help me to clean my code?
                # Thanks you for your help ;)
                parent = False
                name = func.__name__
                for base in self.__class__.mro()[1:]:
                    if parent:
                        if hasattr(base, name):
                            return getattr(base, name)(self, cr, uid, argument, *args, **kwargs)
                    if str(base) == str(self.__class__):
                        #now I am at the good level of the class inherited
                        parent = True
                raise osv.except_osv(_("Not Implemented"), _("Not parent method found"))
                ##### REFACTOR END
        return wrapped
    return decorator


def open_report(func):
    """ This decorator will start and close a report for the function call
    The function must start with "self, cr, uid, object"
    And the object must have a field call "referential_id" related to the object "external.referential"
    """
    @functools.wraps(func)
    def wrapper(self, cr, uid, object, *args, **kwargs):
        if not self._columns.get('referential_id'):
            raise osv.except_osv(_("Not Implemented"), _("The field referential_id doesn't exist on the object %s. Reporting system can not be used" %(self._name,)))

        report_obj = self.pool.get('external.report')
        context = kwargs.get('context')
        if not context:
            context={}
            kwargs['context'] = context
        
        #Start the report
        report_id = report_obj.start_report(cr, uid, id=None, method=func.__name__, object=object, context=context)

        #Execute the original function and add the report_id to the context
        context['report_id'] = report_id
        response = func(self, cr, uid, object, *args, **kwargs)

        #Close the report
        report_obj.end_report(cr, uid, report_id, context=context)

        return response
    return wrapper




def catch_error_in_report(func):
    """ This decorator open and close a new cursor and if an error occure it will generate a error line in the reporting system
    The function must start with "self, cr, uid, object"
    And the object must have a field call "referential_id" related to the object "external.referential"
    """
    @functools.wraps(func)
    def wrapper(self, cr, uid, *args, **kwargs):
        context = kwargs.get('context')
        if not (context and context.get('report_id')):
            raise osv.except_osv(_("Error"), _("There is no key report_id in the context you can not use the decorator in this case"))
        report_line_obj = self.pool.get('external.report.line')
        report_line_id = report_line_obj._log_base(
                                    cr,
                                    uid, 
                                    self._name,
                                    func.__name_, 
                                    state='fail',
                                    external_id=context.get('external_report_id'),
                                    defaults=kwargs.get('defaults'),
                                    data_record=kwargs.get('data_record'), 
                                    context=kwargs.get('context')
                            )

        import_cr = pooler.get_db(cr.dbname).cursor()
        try:
            response = func(self, import_cr, uid, *args, **kwargs)
        except MappingError as e:
            import_cr.rollback()
            report_line_obj.write(cr, uid, report_line_id, {
                            'error_message': 'Error with the mapping : %s. Error details : %s'%(e.mapping_name, e.value),
                            }, context=context)
        except osv.except_osv as e:
            #TODO write correctly the message in the report
            import_cr.rollback()
            raise osv.except_osv(*e)
        except Exception as e:
            #TODO write correctly the message in the report
            import_cr.rollback()
            raise Exception(e)
        else:
            report_line_obj.write(cr, uid, report_line_id, {
                        'state': 'success',
                        }, context=context)
            import_cr.commit()
        finally:
            import_cr.close()
        return response
    return wrapper


