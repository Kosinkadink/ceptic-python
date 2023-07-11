from abc import abstractmethod

import ceptic.stream as cs


class IRemovableManagers(object):
    @abstractmethod
    def handle_new_connection(self, handler: 'cs.StreamHandlerInternal') -> None:
        raise NotImplementedError
