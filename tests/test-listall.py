# Import stock packages
import subprocess

#
# Tests for ListAll.py
#
class TestListAllClass:

    #
    # Make sure that ListAll does not crash with --help
    #
    def test_listall_help(self):
        command = './ListAll.py --help'
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        process.wait()
        assert process.returncode == 0

    #
    # Test config: iam-users-without-mfa-in-select-groups.json
    #
    def test_listall_config_1(self):
        command = './ListAll.py --env sample-001 --config listall-configs/iam-users-without-mfa-in-select-groups.json'
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        process.wait()
        lines = []
        for line in process.stdout:
            lines.append(line.strip())
        assert sorted(lines) == sorted(['MisconfiguredUser-NoMFA', 'l01cd3v-test'])

    #
    # Test config: iam-users-without-mfa-not-in-select-groups.json
    #
    def test_listall_config_2(self):
        command = './ListAll.py --env sample-001 --config listall-configs/iam-users-without-mfa-not-in-select-groups.json'
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        process.wait()
        lines = []
        for line in process.stdout:
            lines.append(line.strip())
        assert sorted(lines) == sorted(['l01cd3v-test'])
