#!/usr/bin/python
# -*- coding: utf-8 -*-
from ansible.plugins.inventory import BaseInventoryPlugin, Constructable, Cacheable
from ansible.errors import AnsibleError
from paramiko import SSHClient
import paramiko
import re

DOCUMENTATION = '''
  name: community.esxi.esxi_inventory
  author:
    - David Danielsson (@djdanielsson)
  plugin_type: inventory
  requirements:
    - ssh enabled on ESXi server
    - paramiko python package
  version_added: "0.1.0"
  short_description: Generate inventory from ESXi
  description: Generate inventory from powered on VM's running on ESXi
  extends_documentation_fragment:
    - constructed
  options:
    hostname:
      description: The ESXi hypervisor's FQDN/IP
      required: true
      type: string
      default: none
    username:
      description: Username to login to ESXi CLI
      required: true
      type: string
      default: none
    password:
      description: Password for provided user
      required: true
      env:
        - name: ESXI_PASSWORD
    group_by:
      description:
        - Keys used to create groups from.
      type: list
      elements: str
      required: false
      choices:
        - guestfamily
        - guestid
        - geststate
        - notes
      default: []
  notes:
    - This currently only returns VM's that are powered on
'''

EXAMPLES = '''
# Minimal example
plugin: community.esxi.esxi_inventory
hostname: 'hypervisor.example.com'
username: 'root'

# Fully loaded
plugin: community.esxi.esxi_inventory
hostname: 'hypervisor.example.com'
username: 'root'
group_by:
  - guestfamily
  - guestid
  - geststate
  - notes
'''

def _populate(self, params):
  client = SSHClient()
  client.load_system_host_keys()
  client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  try:
    client.connect(params['hostname'], username=params['username'], password=params['password'] )
  except:
    print("connection issue")

  try:
    stdin_, stdout_, stderr_= client.exec_command('vim-cmd vmsvc/getallvms | awk \'{ print $1 }\' | grep -v Vmid')
    ids = stdout_.read().decode().strip()
    _stderr = stderr_.read().decode()
  except:
    ignoreError = True
    # print("exec command issue %s " % ids)
    # print("stderr: %s" % _stderr)

  # print(ids)
  for id in ids.splitlines():
    vminfo = ''
    vmsummary = ''
    # print(id)
    _command = 'vim-cmd vmsvc/get.guest ' + id
    try:
      _stdin, _stdout, _stderr= client.exec_command(_command)
      vminfo = _stdout.read().decode()
    except:
      print("exec command on %s command" % _command)
      print("exec command issue %s " % vminfo)

    _summary = 'vim-cmd vmsvc/get.summary ' + id
    try:
      _stdin, _stdout, _stderr= client.exec_command(_summary)
      vmsummary = _stdout.read().decode()
    except:
      print("exec command on %s command" % _summary)
      print("exec command issue %s " % vmsummary)

    #print(vminfo)
    # hostname    = ''
    # ipaddress   = ''
    # guestfamily = ''
    # guestid     = ''
    # geststate   = ''
    # notes       = ''
    try:
      hostname    = (re.search('hostName\s=\s\"(.*)\",', vminfo)).group(1)
      ipaddress   = (re.search('ipAddress\s=\s\"(([\d]{1,3}.){4})\",', vminfo)).group(1) # or "")
      guestfamily = (re.search('guestFamily(.*)\s=\s\"(.*)\",', vminfo)).group(2)
      guestid     = (re.search('guestId(.*)\s=\s\"(.*)\",', vminfo)).group(2)
      geststate   = (re.search('guestState\s=\s\"(.*)\",', vminfo)).group(1) # or ((re.search('powerState\s=\s\"(.*)\",', vminfo)).group(1))
      notes       = ((re.search('annotation\s=\s\"(.*)\",', vmsummary)).group(1) or "")
    except:
      ignoreError = True

    self.inventory.add_host(hostname)
    self.inventory.set_variable(hostname, 'ansible_host', ipaddress)
    self.inventory.set_variable(hostname, 'guest_family', guestfamily)
    self.inventory.set_variable(hostname, 'guest_name', guestid)
    self.inventory.set_variable(hostname, 'vm_state', geststate)
    self.inventory.set_variable(hostname, 'esxi_uid', id)
    self.inventory.set_variable(hostname, 'notes', notes)

    if params['group_by'] != []:
      if 'guestfamily' in params['group_by']:
        if guestfamily != "":
          self.inventory.add_group(guestfamily)
          self.inventory.add_child('all', guestfamily)
          self.inventory.add_child(guestfamily, hostname)

      if 'guestid' in params['group_by']:
        if guestid != "":
          self.inventory.add_group(guestid)
          self.inventory.add_child('all', guestid)
          self.inventory.add_child(guestid, hostname)

      # commenting out because currently only getting running VMs
      # if 'geststate' in params['group_by']:
      #   if geststate != "":
      #     self.inventory.add_group(geststate)
      #     self.inventory.add_child('all', geststate)
      #     self.inventory.add_child(geststate, hostname)

      if 'notes' in params['group_by']:
        if notes != "":
          self.inventory.add_group(notes)
          self.inventory.add_child('all', notes)
          self.inventory.add_child(notes, hostname)

  client.close()

class InventoryModule(BaseInventoryPlugin, Constructable, Cacheable):
  NAME = 'community.esxi.esxi_inventory'

  def verify_file(self, path):
    # return true/false if this is possibly a valid file for this plugin to consume
    valid = False
    if super(InventoryModule, self).verify_file(path):
    # base class verifies that file exists and is readable by current user
      if path.endswith(('esxi.yaml', 'esxi.yml', 'esxi_inventory.yaml', 'esxi_inventory.yml')):
        valid = True
    return valid

  def parse(self, inventory, loader, path, cache = True): #Return dynamic inventory from source
    super(InventoryModule, self).parse(inventory, loader, path, cache)

    config = self._read_config_data(path)
    self._consume_options(config)

    params = {}
    params['hostname'] = self.get_option('hostname')
    params['username'] = self.get_option('username')
    params['password'] = self.get_option('password')
    params['group_by'] = self.get_option('group_by')

    if params['hostname'] == "":
      raise AnsibleError("Missing required value 'hostname'")
    if params['username'] == "":
      raise AnsibleError("Missing required value 'username'")
    if params['password'] == "":
      raise AnsibleError("Missing required value 'password'")

    results = _populate(self, params)
