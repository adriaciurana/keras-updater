import zmq, json, sys
from enum import IntEnum
from threading import Thread
from keras.callbacks import Callback
import keras.backend as K

class Updater(type):
    
    RESTRICTIONS = {
        'params': {
            'batch_size': True
        }
    }
    
    """
        DEFINITIONS
    """
    class OPERATIONS(IntEnum):
        UPDATE, ONE_EPOCH = range(2)

    class RESPONSES(IntEnum):
        OK, WAIT, ERROR = range(3)

    class PRIORITIES(IntEnum):
        NORMAL, HIGH, VERY_HIGH = range(3)
    NEXT = 'next'
    
    """
        Call method
    """
    @staticmethod
    def __new__(self, *vargs, **kwargs):
        callback = Updater.UpdaterInstance(*vargs, **kwargs)
        return [callback] + list(callback.callbacks.values())

    """
        CREDENTIALS
    """
    @staticmethod
    def obtain_credentials(credentials):
        if credentials is None:
            # No user/password
            return None
        
        elif isinstance(credentials, (tuple, list)):
            # user, password
            if len(credentials) == 1:
                user = "root"
                password = credentials[0]
            elif len(credentials) == 2:
                user = credentials[0]
                password = credentials[1]

        elif isinstance(credentials, dict):
            # user/password
            user = credentials['user']
            password = credentials['password']

        elif isinstance(credentials, str):
            # user:password
            if ':' in credentials:
                user, password = credentials.split(':')
            else:
                user = "root"
                password = credentials

        return {'user': user, 'password': password}
    
    """
        RESTRICTIONS
    """
    @staticmethod
    def clear_restrictions(config):
        restriction_list = []
        def __recusirve_restrictions(path, config, restrictions):
            for k, v in restrictions.items():
                if isinstance(v, dict):
                    if isinstance(config, dict):
                        next_config = config[k]
                    elif k in pointer.__dict__:
                        next_config = getattr(config, k)     
                    __recusirve_restrictions(path + [k], next_config, v)

                else:
                    if isinstance(config, dict):
                        config_dict = config
                    else:
                        config_dict = config.__dict__
                    if k in config_dict and restrictions[k]:
                        restriction_list.append('->'.join(path) + '->' + str(k))
                        del config[k]
        __recusirve_restrictions([], config, Updater.RESTRICTIONS)
        return restriction_list

    """
        PARSERS
    """
    @staticmethod
    def parse_epoch(epoch):
        if isinstance(epoch, str) and epoch == 'next':
            return Updater.NEXT
        elif not isinstance(epoch, int):
            raise IndexError
        return str(epoch)

    @staticmethod
    def parse_operation(operation):
        if isinstance(operation, str):
            if operation.lower() == 'update':
                operation = Updater.OPERATIONS.UPDATE
            elif operation.lower() == 'next_epoch':
                operation = Updater.OPERATIONS.ONE_EPOCH
        elif not isinstance(operation, Updater.OPERATIONS):
            raise IndexError
        return operation

    @staticmethod
    def parse_priority(priority):
        if isinstance(priority, str):
            if priority.lower() == 'normal':
                priority = Updater.PRIORITIES.NORMAL
            elif priority.lower() == 'high':
                priority = Updater.PRIORITIES.HIGH
            elif priority.lower() == 'very high':
                priority = Updater.PRIORITIES.VERY_HIGH
        elif not (isinstance(priority, Updater.PRIORITIES) or isinstance(priority, int)):
            raise IndexError
        return priority

    @staticmethod
    def package_generator(operation, priority, callbacks, model, params, metrics):
        return {
            'operation': Updater.parse_operation(operation),
            'priority': Updater.parse_priority(priority),
            'config': {
                'callbacks': callbacks,
                'model': model,
                'params': params,
                'metrics': metrics
            }
        }

    @staticmethod
    def send_package(socket, msg_obj):
        msg_raw = json.dumps(msg_obj)
        socket.send_string(msg_raw)

    @staticmethod
    def read_package(socket):
        msg_raw = socket.recv()
        return json.loads(msg_raw.decode('utf-8'))


    # Client to use in IPython (for instance) or other processes.
    class Client(object):
        def __init__(self, ip='127.0.0.1:1717', credentials=None):
            self.ip = ip
            self.credentials = Updater.obtain_credentials(credentials)

            context = zmq.Context()
            print("Connecting to server...", end="")
            self.socket = context.socket(zmq.REQ)
            self.socket.connect("tcp://%s" % self.ip)
            print(" done")

        def __send_operation(self, container):
            print("Sending new config to server...", end="")
            messages = []

            # If restriction
            for epoch, config in container.items():
                restriction_list = Updater.clear_restrictions(config['config'])
                if len(restriction_list) > 0:
                    messages.append('The following variables in epoch %s are restricted: %s.' % (str(epoch), ', '.join(restriction_list)))
             
            msg_obj = {
                'credentials': self.credentials,
                'container': container
            }
            Updater.send_package(self.socket, msg_obj)
            #msg_raw = json.dumps(msg_obj)
            #self.socket.send_string(msg_raw)
            print(" done")

            if len(messages) > 0:
                print('\n'.join(messages))
                        
            # Response
            is_first = True
            while True:
                #msg_raw = self.socket.recv()
                #msg_obj = json.loads(msg_raw)
                msg_obj = Updater.read_package(self.socket)

                if msg_obj['response'] == Updater.RESPONSES.WAIT:
                    if is_first:
                        print("")
                        is_first = False

                    if 'messages' in msg_obj and len(msg_obj['messages']) > 0:
                        print('\n'.join(msg_obj['messages']))
                else:
                    break

            if 'messages' in msg_obj and len(msg_obj['messages']) > 0:
                print('\n'.join(msg_obj['messages']))
            return msg_obj['response'] == Updater.RESPONSES.OK

        def only_one_epoch_config(self, epoch='next', callbacks={}, model={}, params={}, metrics={}):
            return self.__send_operation({
                Updater.parse_epoch(epoch): Updater.package_generator(Updater.OPERATIONS.ONE_EPOCH, -1, callbacks, model, params, metrics)
            })

        def update_config(self, epoch='next', priority='normal', callbacks={}, model={}, params={}, metrics={}):
            return self.__send_operation({
                Updater.parse_epoch(epoch): Updater.package_generator(Updater.OPERATIONS.UPDATE, priority, callbacks, model, params, metrics)
            })

        def start_schedule_config(self):
            self.schedule_list = {}

        def add_schedule_config_step(self, epoch, operation='update', priority='normal', callbacks={}, model={}, params={}, metrics={}):
            self.schedule_list[Updater.parse_epoch(epoch)] = Updater.package_generator(operation, priority, callbacks, model, params, metrics) 

        def end_schedule_config(self):
            if len(self.schedule_list) > 0:
                aux = self.__send_operation(self.schedule_list)
                self.schedule_list = {}
                return aux
            return False

    class UpdaterInstance(Callback):
        """
            ADD UPDATES METHODS
        """
        def __add_container(self, container, messages):
            # Read every epoch
            for epoch, next_config in container.items():
                # Check restrictions and remove
                restriction_list = Updater.clear_restrictions(next_config['config'])
                if epoch not in self.temp_epoch_config:
                    self.temp_epoch_config[epoch] = []

                # Add any config in the correspondent epoch
                self.temp_epoch_config[epoch].append({
                    'operation': next_config['operation'],
                    'priority': next_config['priority'],
                    'config': next_config['config']
                })

                # Add messages about restriccions
                if len(restriction_list) > 0:
                     messages.append('The following variables in epoch %s are restricted: %s.' % (str(epoch), ', '.join(restriction_list)))

        def __do_operation(self, container):
            try:
                print("Sending new config to server...", end="")
                messages = []

                self.__add_container(self, container, messages)
                print(" done")

                result = True
            except Exception as e:
                messages.append('Exception: %s' % str(e))
                result = False

            if len(messages) > 0:
                print('\n'.join(messages))
 
            return result

        def only_one_epoch_config(self, epoch='next', callbacks={}, model={}, params={}, metrics={}):
            return self.__do_operation({
                Updater.parse_epoch(epoch): Updater.package_generator(Updater.OPERATIONS.ONE_EPOCH, -1, callbacks, model, params, metrics)
            })

        def update_config(self, epoch='next', priority='normal', callbacks={}, model={}, params={}, metrics={}):
            return self.__do_operation({
                Updater.parse_epoch(epoch): Updater.package_generator(Updater.OPERATIONS.UPDATE, priority, callbacks, model, params, metrics)
            })

        def start_schedule_config(self):
            self.schedule_list = {}

        def add_schedule_config_step(self, epoch, operation='update', priority='normal', callbacks={}, model={}, params={}, metrics={}):
            self.schedule_list[Updater.parse_epoch(epoch)] = Updater.package_generator(operation, priority, callbacks, model, params, metrics) 

        def end_schedule_config(self):
            if len(self.schedule_list) > 0:
                aux = self.__do_operation(self.schedule_list)
                self.schedule_list = {}
                return aux
            return False

        """
            RESPONSE
        """
        def send_response(self, response, messages):
            Updater.send_package(self.socket, {'response': response, 'messages': messages})

        """
            CONSUMER ZMQ MESSAGES
        """
        def __thread_client_consumer(self):
            # Infinite loop to read messages
            while not self.__stop_loop:
                try:
                    # Init messages
                    messages = []

                    # Read message
                    msg_raw = self.socket.recv()
                    msg_obj = json.loads(msg_raw.decode('utf-8'))

                    # Check credentials
                    if self.credentials is not None:
                        if 'credentials' not in msg_obj or \
                            msg_obj['credentials'] is None or \
                            msg_obj['credentials']['user'] != self.credentials['user'] or \
                            msg_obj['credentials']['password'] != self.credentials['password']:
                            messages.append('Wrong credentials.')
                            continue

                    # Load container
                    container = msg_obj['container']

                    self.__add_container(container, messages)
                    messages.append("Enqueued config.")
                    
                    # Send the message to client
                    self.send_response(Updater.RESPONSES.OK, messages)
                
                except Exception as e:
                    # Send the error message to client
                    messages.append('Exception during enqueuing: %s' % str(e))
                    self.send_response(Updater.RESPONSES.ERROR, messages)

        def __init__(self, ip='127.0.0.1:1717', credentials=None, callbacks={}):
            super(Updater.UpdaterInstance, self).__init__()

            # Configuration about server
            self.credentials = Updater.obtain_credentials(credentials)
            self.ip = ip

            # Queues and change reverses
            self.temp_epoch_config = {}
            self.temp_changes = None

            # Socket config            
            context = zmq.Context()
            self.socket = context.socket(zmq.REP)
            self.socket.bind("tcp://%s" % self.ip)

            self.__stop_loop = False
            self.thread = Thread(target=self.__thread_client_consumer)
            self.thread.start()

            # Callbacks that Updater has access
            self.callbacks = {}
            self.add_callbacks(callbacks)

        def __call__(self, *vargs, **kwargs):
            self.add_callbacks(vargs)
            self.add_callbacks(kwargs)

        def add_callbacks(self, callbacks):
            if isinstance(callbacks, dict):
                self.callbacks.update(callbacks)
            elif isinstance(callbacks, (list, tuple)):
                for c in callbacks:
                    self.callbacks[c.__class__.__name__] = c
            else:
                self.callbacks[callbacks.__class__.__name__] = callbacks

        def __update_config(self, config):
            def __parse_element(element, value):
                
                if isinstance(element, K.tf.Variable):
                    # Parse to tf.Variable
                    return K.tf.Variable(value)
                else:
                    # Map variable->variable
                    return value

            def __recusirve_config(pointer, params):
                changes = {}
                
                for k, v in params.items():
                    # If params are more deeper
                    if isinstance(v, dict):
                        # If pointer are also an dict
                        if isinstance(pointer, dict):
                            next_pointer = pointer[k]
                        # If pointer are a object
                        elif k in pointer.__dict__:
                            next_pointer = getattr(pointer, k)
                        # Again do recursive config
                        changes[k] = __recusirve_config(next_pointer, v)
                    else:
                        # If pointer are a dict, parse element and set into the pointer
                        if isinstance(pointer, dict):
                            changes[k] = pointer[k]
                            pointer[k] = __parse_element(changes[k], v)
                        # If pointer are a object, parse element and set into the pointer
                        elif k in pointer.__dict__:
                            changes[k] = getattr(pointer, k)
                            setattr(pointer, k, __parse_element(changes[k], v))
                    
                return changes
            
            changes = {}

            # Callbacks
            if 'callbacks' in config:
                changes['callbacks'] = __recusirve_config(self.callbacks, config['callbacks'])

            # model
            if 'model' in config:
                changes['model'] = __recusirve_config(self.model, config['model'])

            # params
            """if 'params' in config:
                changes['params'] = __recusirve_config(self.params, config['params'])"""

            # model
            """if 'model' in config:
                changes['model'] = __recusirve_config(self.model, config['model'])"""

            return changes

        def on_train_begin(self, logs=None):
            super(Updater.UpdaterInstance, self).on_train_begin(logs)

        def on_epoch_end(self, epoch, logs=None):
            def __get_config_current_epoch(epoch):
                configs = self.temp_epoch_config.pop(epoch, None)

                if configs is not None:
                    configs.sort(reverse=False, key=lambda x: x['priority'])
                    return configs
                
                return None
           
            def __recursive_merge_changes(changes_part, changes):
                for k, v in changes_part.items():
                    if isinstance(v, dict):
                        if k not in changes:
                            changes[k] = {}
                        __recursive_merge_changes(v, changes[k])
                    else:
                        changes.setdefault(k, v)
            
            epoch_1 = epoch + 1
            try:
                messages = []
                # 1- Revert old changes in last epochs
                if self.temp_changes is not None:
                    self.__update_config(self.temp_changes)
                    self.temp_changes = None
             
                # 2- Get configs scheduled
                has_configs = False
                configs = __get_config_current_epoch(str(epoch_1))
                if configs is not None:
                    has_configs = True
                    for config in configs:
                        self.__update_config(config['config'])

                # 3- Get configs next epoch
                configs = self.temp_epoch_config.pop(Updater.NEXT, None)
                if configs is not None:
                    has_configs = True
                    self.temp_changes = {}
                    for config in configs:
                            changes_part = self.__update_config(config['config'])
                            if config['operation'] == Updater.OPERATIONS.ONE_EPOCH:
                                __recursive_merge_changes(changes_part, self.temp_changes)
                
                # 4- Run parent
                super(Updater.UpdaterInstance, self).on_epoch_end(epoch, logs)

                # 5- Response
                #if has_configs:
                #    self.send_response(Updater.RESPONSES.OK, ["The %s epoch is correct processed." % epoch_1])
            except Exception as e:
                # Avoid crashes during training
                messages.append('Exception during execution: %s' % str(e))
                self.send_response(Updater.RESPONSES.ERROR, messages)
                
        def on_train_end(self, logs=None):
            super(Updater.UpdaterInstance, self).on_train_end(logs)
            self.__stop_loop = True
            self.socket.close()
            del self.socket
