# vim: tabstop=4 shiftwidth=4 softtabstop=4

#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import abc
import collections
import functools

from heat.db import api as db_api


class Template(collections.Mapping):
    '''A stack template.'''

    def __new__(cls, template, *args, **kwargs):
        '''Create a new Template of the appropriate class.'''

        if cls == Template:
            # deferred module imports to avoid circular dependency
            if 'heat_template_version' in template:
                from heat.engine import hot
                return hot.HOTemplate(template, *args, **kwargs)
            else:
                from heat.engine.cfn import template as cfn
                return cfn.CfnTemplate(template, *args, **kwargs)

        return super(Template, cls).__new__(cls)

    def __init__(self, template, template_id=None, files=None):
        '''
        Initialise the template with a JSON object and a set of Parameters
        '''
        self.id = template_id
        self.t = template
        self.files = files or {}
        self.maps = self[self.MAPPINGS]

    @classmethod
    def load(cls, context, template_id):
        '''Retrieve a Template with the given ID from the database.'''
        t = db_api.raw_template_get(context, template_id)
        return cls(t.template, template_id=template_id, files=t.files)

    def store(self, context=None):
        '''Store the Template in the database and return its ID.'''
        if self.id is None:
            rt = {
                'template': self.t,
                'files': self.files
            }
            new_rt = db_api.raw_template_create(context, rt)
            self.id = new_rt.id
        return self.id

    def __iter__(self):
        '''Return an iterator over the section names.'''
        return (s for s in self.SECTIONS
                if s not in self.SECTIONS_NO_DIRECT_ACCESS)

    def __len__(self):
        '''Return the number of sections.'''
        return len(self.SECTIONS) - len(self.SECTIONS_NO_DIRECT_ACCESS)

    @abc.abstractmethod
    def param_schemata(self):
        '''Return a dict of parameters.Schema objects for the parameters.'''
        pass

    @abc.abstractmethod
    def parameters(self, stack_identifier, user_params, validate_value=True,
                   context=None):
        '''Return a parameters.Parameters object for the stack.'''
        pass

    @abc.abstractmethod
    def functions(self):
        '''Return a dict of template functions keyed by name.'''
        pass

    def parse(self, stack, snippet):
        parse = functools.partial(self.parse, stack)

        if isinstance(snippet, collections.Mapping):
            if len(snippet) == 1:
                fn_name, args = next(snippet.iteritems())
                Func = self.functions().get(fn_name)
                if Func is not None:
                    return Func(stack, fn_name, parse(args))
            return dict((k, parse(v)) for k, v in snippet.iteritems())
        elif (not isinstance(snippet, basestring) and
              isinstance(snippet, collections.Iterable)):
            return [parse(v) for v in snippet]
        else:
            return snippet
