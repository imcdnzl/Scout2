from AWSScout2.finding import *

#
# RDS findings
#
class RdsFinding(Finding):

    def __init__(self, description, entity, callback, callback_args, level, questions):
        self.keyword_prefix = 'rds'
        Finding.__init__(self, description, entity, callback, callback_args, level, questions)

    def checkInternetAccessible(self, key, obj):
        for ip_range in obj['ip_ranges']:
            if ip_range == '0.0.0.0/0':
                self.addItem(obj['name'])

    def checkMultiAZ(self, key, obj):
        if not obj['MultiAZ']:
            self.addItem(obj['DBInstanceIdentifier'])

    def checkAutoUpgrade(self, key, obj):
        if not obj['AutoMinorVersionUpgrade']:
            self.addItem(obj['DBInstanceIdentifier'])

    def checkPostgresCreationDate(self, key, obj):
        if (obj['Engine'].lower() == 'postgres'):
            if self.wasCreatedBefore(key, obj):
                self.addItem(obj['DBInstanceIdentifier'])
