"""from modelcheckpointupdater import ModelCheckpointUpdater
client = ModelCheckpointUpdater.Client(credentials=('root', '1234'))
print(client.update_config(verbose=True, period=1))"""

from updater import Updater
client = Updater.Client(credentials=('root', '1234'))
#client.start_schedule_config()
client.update_config(
	callbacks={
		'ModelCheckpoint': 
			{
				'save_best_only': True,
				'verbose': True, 
				'period': 1
			}
		},
	model={
		'optimizer': {
			'lr': 0.000000000000000000000000
		}
	},
	params={'batch_size': 1, 'epochs': 10000}
)
#print(client.end_schedule_config())
