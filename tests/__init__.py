# Import stock packages
import subprocess

#
# Set up
#
def setUp(self):
    command = 'for d in `ls -d tests/*/`; do test="`basename $d`"; ln -s $d inc-awsconfig-$test; done'
    process = subprocess.Popen(command, shell=True)
    process.wait()

def teardown(self):
    command = 'find -maxdepth 1 -type l -delete'
    process = subprocess.Popen(command, shell=True)
    process.wait()
