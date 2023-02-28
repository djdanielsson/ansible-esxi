from ansible.plugins.inventory import BaseInventoryPlugin, Constructable, Cacheable
from ansible.errors import AnsibleError
from paramiko import SSHClient
import paramiko
import re

DOCUMENTATION = '''
  name: community.esxi.esxi_inventory
  plugin_type: inventory
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
      type: string
      default: none
'''

EXAMPLES = '''
# Minimal example
plugin: community.esxi.esxi_inventory
hostname: 'hypervisor.example.com'
username: 'root'
password: 'Password'
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
    stdin_, stdout_, stderr_= client.exec_command('vim-cmd vmsvc/getallvms | grep -v Vmid | awk \'{ print $1 }\'')
    ids = stdout_.read().decode().strip()
    _stderr = stderr_.read().decode()
  except:
    ignoreError = True
    # print("exec command issue %s " % ids)
    # print("stderr: %s" % _stderr)

  # print(ids)
  for id in ids.splitlines():
    # print(id)
    _command = 'vim-cmd vmsvc/get.guest ' + id
    try:
      _stdin, _stdout, _stderr= client.exec_command(_command)
      vminfo = _stdout.read().decode()
    except:
      print("exec command on %s command" % _command)
      print("exec command issue %s " % vminfo)

    #print(vminfo)
    try:
      hostname    = (re.search('hostName\s=\s\"(.*)\",', vminfo)).group(1)
      ipaddress   = (re.search('ipAddress\s=\s\"(([\d]{1,3}.){4})\",', vminfo)).group(1)
      guestfamily = (re.search('guestFamily(.*)\s=\s\"(.*)\",', vminfo)).group(2)
      guestid     = (re.search('guestId(.*)\s=\s\"(.*)\",', vminfo)).group(2)
      geststate   = (re.search('guestState\s=\s\"(.*)\",', vminfo)).group(1)
    except:
      ignoreError = True

    self.inventory.add_host(hostname)
    self.inventory.set_variable(hostname, 'ansible_host', ipaddress)
    self.inventory.set_variable(hostname, 'guest_family', guestfamily)
    self.inventory.set_variable(hostname, 'guest_name', guestid)
    self.inventory.set_variable(hostname, 'vm_state', geststate)

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

    results = _populate(self, params)
