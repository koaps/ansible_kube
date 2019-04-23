#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = """
---
module: kube
short_description: Manage Kubernetes Cluster
description:
  - Run commands against a Kubernetes Cluster
version_added: "2.6"
options:
  kubectl:
    required: false
    default: null
    description:
      - The path to the kubectl bin
  command:
    required: false
    default: apply
    description:
      - The command operation to run, defaults to apply
      - See: https://kubernetes.io/docs/reference/kubectl/overview/#operations
  resource:
    required: false
    default: null
    description:
      - The resource type to perform an action on. pods (po), replicationControllers (rc), services (svc)
      - See: https://kubernetes.io/docs/reference/kubectl/overview/#resource-types
      - Resources can have sub-names, in this case specify the resource as a list.
    aliases: [ 'resources' ]
  name:
    required: false
    default: null
    description:
      - The name associated with resource.
  keyvars:
    required: false
    default: null
    description:
      - The key=value pairs used for the resource.
      - Several pairs can be specified using a comma separated list.
  filter:
    required: false
    default: null
    description:
      - Run a regex findall against the stdout of the kubectl command
  filename:
    required: false
    default: null
    description:
      - The path and filename of the resource(s) definition file(s).
      - To operate on several files this can accept a comma separated list of files or a list of files.
    aliases: [ 'files', 'file', 'filenames' ]
  namespace:
    required: false
    default: null
    description:
      - The namespace associated with the resource(s), shortcut for ---namespace flag
  label:
    required: false
    default: null
    description:
      - The labels used to filter specific resources, shortcut for --selector flag
  server:
    required: false
    default: null
    description:
      - The url for the API server that commands are executed against, shortcut for --server flag
  kubeconfig:
    required: false
    default: null
    description:
      - Specifcy the kubeconfig to use, shortcut for ---kubeconfig flag
  ignore:
    required: false
    default: false
    description:
      - A flag to indicate ignore not found errors, shortcut for --ignore-not-found flag
    type: bool
  overwrite:
    required: false
    default: false
    description:
      - A flag to indicate overwrite existing, shortcut for --overwrite flag
    type: bool
  force:
    required: false
    default: false
    description:
      - A flag to indicate force delete, replace, or stop, shortcut for --force flag
    type: bool
  all:
    required: false
    default: false
    description:
      - A flag to indicate delete all, stop all, or all namespaces when checking exists, shortcut for --all flag
    type: bool
  log_level:
    required: false
    default: 0
    description:
      - Indicates the level of verbosity of logging by kubectl.
    type: int
  state:
    required: false
    choices: ['present', 'absent', 'latest']
    default: present
    description:
      - present handles checking existence or creating if definition file provided,
        absent handles deleting resource(s) based on other options,
        latest handles creating or updating based on existence,
requirements:
  - kubectl
"""

EXAMPLES = """
- name: test nginx is present (default)
  kube:
    name: nginx
    resource: rc

- name: test nginx is absent
  kube:
    name: nginx
    resource: rc
    state: absent

- name: test nginx is latest
  kube:
    filename: /tmp/nginx.yml
    state: latest
"""

class KubeManager(object):

  def __init__(self, module):
    self.module = module
    self.kubectl = module.params.get('kubectl')
    if self.kubectl is None:
      self.kubectl =  module.get_bin_path('kubectl', True)
    self.base_cmd = [self.kubectl]
    self.command = module.params.get('command')
    self.resource = [r.strip() for r in module.params.get('resource') or []]
    self.name = module.params.get('name')
    self.keyvars = [k.strip() for k in module.params.get('keyvars') or []]
    self.filter = module.params.get('filter')
    self.filename = [f.strip() for f in module.params.get('filename') or []]
    self.namespace = module.params.get('namespace')
    self.label = module.params.get('label')
    self.server = module.params.get('server')
    self.kubeconfig = module.params.get('kubeconfig')
    self.ignore = module.params.get('ignore')
    self.overwrite = module.params.get('overwrite')
    self.force = module.params.get('force')
    self.all = module.params.get('all')
    self.log_level = module.params.get('log_level')
    self.safe_commands = ['api-versions','cluster-info','describe','explain','get','logs','version']
    self.changed_words = ['created','deleted','labeled','modified']
    self.isdir = False
    self.results = {'changed': False, 'meta': [], 'msg': ''}

    if self.filename:
      import os
      if os.path.isdir(self.filename[0]):
        self.isdir = True

    if self.filter:
      import json
      import re

  def _execute(self, cmd, exists=False):
    args = self.base_cmd + cmd
    try:
      rc, out, err = self.module.run_command(args)
      if rc != 0 and not (exists or self.isdir):
        self.module.fail_json(msg='error running kubectl (%s) command (rc=%d), out=\'%s\', err=\'%s\'' % (' '.join(args), rc, out, err))
      elif rc != 0 and exists and ' '.join(err.split()[-2:]) == 'not found':
        return
      else:
        if self.filter:
          self.results['meta'] = self._filter(self.filter, out)
        else:
          self.results['meta'] = out.splitlines()
          if self.results['meta'] != [] and filter(lambda item: any(x in item for x in out.split()), self.changed_words):
            self.results['changed'] = True
          self.results['msg'] = 'successfully ran kubectl (%s) command' % (self.command)
    except Exception as exc:
      self.module.fail_json(msg='error running kubectl (%s) command: %s' % (' '.join(args), str(exc)))

  def _exists(self):
    cmd = ['get']
    cmd = self._flags(cmd, exists=True)
    self._execute(cmd, exists=True)
    if self.results['meta'] != []:
        return True
    return False

  def _flags(self, cmd, exists=False):
    if not self.filename and not self.resource:
      self.module.fail_json(msg='filename or resource required')
    if self.resource:
      if exists:
        cmd.append(self.resource[0])
      else:
        for r in self.resource: cmd.append(r)
    if self.name:
      cmd.append(self.name)
    if self.keyvars:
      if not exists:
        for kv in self.keyvars: cmd.append(kv)
    if self.filename:
      cmd.append('--filename=' + ','.join(self.filename))
    if self.kubeconfig:
      cmd.append('--kubeconfig=' + self.kubeconfig)
    if self.namespace:
      cmd.append('--namespace=' + self.namespace)
    if self.label:
      cmd.append('--selector=' + self.label)
    if self.server:
      cmd.append('--server=' + self.server)
    if self.ignore:
      cmd.append('--ignore-not-found')
    if self.overwrite:
      cmd.append('--overwrite')
    if self.force:
      cmd.append('--force')
    if self.all:
      cmd.append('--all')
    if self.log_level:
      cmd.append('--v=' + str(self.log_level))
    if cmd[0] == 'get':
      cmd.append('--no-headers')
    return cmd

  def _filter(self, filter, string):
    return re.findall(filter, string)

  def create(self, check=True):
    if self.command == 'delete':
      self.module.fail_json(msg="use state=absent instead of command=delete")
    if check and self._exists() and self.command not in self.safe_commands:
      return
    cmd = [self.command]
    cmd = self._flags(cmd)
    self._execute(cmd)

  def delete(self):
    if not self.force and not self._exists():
      return
    self.command = 'delete'
    cmd = ['delete']
    cmd = self._flags(cmd)
    self._execute(cmd)

def main():
  module = AnsibleModule(
    argument_spec=dict(
      kubectl=dict(type='str'),
      command=dict(default='apply', type='str'),
      resource=dict(type='list', aliases=['resources']),
      name=dict(type='str'),
      keyvars=dict(type='list'),
      filter=dict(type='str'),
      filename=dict(type='list', aliases=['files', 'file', 'filenames']),
      namespace=dict(type='str'),
      label=dict(type='str'),
      server=dict(type='str'),
      kubeconfig=dict(type='str'),
      ignore=dict(default=False, type='bool'),
      overwrite=dict(default=False, type='bool'),
      force=dict(default=False, type='bool'),
      all=dict(default=False, type='bool'),
      log_level=dict(default=0, type='int'),
      state=dict(default='present', choices=['present', 'absent', 'latest', 'reloaded', 'stopped']),
    ),
    mutually_exclusive=[
      ['filename', 'resource'],
      ['filename', 'name'],
      ['namespace', 'all']
    ]
  )
  kubeman = KubeManager(module)
  state = module.params.get('state')
  if state == 'present':
    kubeman.create()
  elif state == 'absent':
    kubeman.delete()
  elif state == 'latest':
    self.overwrite = True
    kubeman.create(check=False)
  else:
    module.fail_json(msg='Unrecognized state %s.' % state)
  module.exit_json(**kubeman.results)

from ansible.module_utils.basic import *
if __name__ == '__main__':
  main()
