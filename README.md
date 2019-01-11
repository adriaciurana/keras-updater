# keras-updater
Keras updater is a very simple callback that allows to modify while the model is training parameters of: training, optimizer, layers, etc.

This callback generates a daemon based on a **zmq** communication. It also includes a simple credential system to make sure that no one without access enters to modify the model.

In this way, using another terminal such as IPython, you can send change requests to be made.



![](doc/doc.png)

In keras-updater there are different modes of action:

- Permanent update (update_config).
- Update in an era (only_one_epoch_config).
- Configure a scheduling to define in each epoch what changes to make (start_schedule_config, add_schedule_config_step, end_schedule_config). Whether it is a permanent change from that time or only that.

In addition, the possibility of defining priorities is provided in case different changes have to be applied where the most important change will prevail.



## Examples

Using keras-updater is very simple. You only have to add Updater to the callbacks of the model you want to train, Updater by default returns a list. So it should be included like this:

```
model.fit(x_train, y_train,
          batch_size=batch_size,
          epochs=epochs,
          verbose=1,
          validation_data=(x_test, y_test),
          callbacks=[othercallback] + Updater(credentials=('root', '1234')))
```

The reason for this is that Updater is also capable of modifying other callbacks! For this reason, they can be included in it so that they can be modified when desired.

```
model.fit(x_train, y_train,
          batch_size=batch_size,
          epochs=epochs,
          verbose=1,
          validation_data=(x_test, y_test),
          callbacks=Updater(credentials=('root', '1234'), callbacks=[ModelCheckpoint(filepath='model.{epoch:02d}-{val_loss:.2f}.h5', period=10000)]))
score = model.evaluate(x_test, y_test, verbose=0)
```

## Collaborations

Any collaborations are welcomes, it is very early stage project.