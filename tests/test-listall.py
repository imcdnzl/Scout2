# Import stock packages
import subprocess

#
# Tests for ListAll.py
#
class TestListAllClass:

    #
    # Bleh
    #
    listall_configs = [
        ['sample-001', 'iam-users-without-mfa-in-select-groups.json', ['MisconfiguredUser-NoMFA', 'l01cd3v-test']],
        ['sample-001', 'iam-users-without-mfa-not-in-select-groups.json', ['l01cd3v-test']]
    ]

    #
    # Make sure that ListAll does not crash with --help
    #
    def test_listall_help(self):
        command = './ListAll.py --help'
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        process.wait()
        assert process.returncode == 0

    #
    # Test all configs
    #
    def test_listall_configs(self):
        all_passed = True
        for config in self.listall_configs:
            command = './ListAll.py --env %s --config listall-configs/%s' % (config[0], config[1])
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            process.wait()
            lines = []
            for line in process.stdout:
                lines.append(str(line.strip()))
            if sorted(lines) != sorted(config[2]):
                print('Error when testing %s :: %s does not match %s' % (config[1], lines, config[2]))
                all_passed = False
        assert all_passed
