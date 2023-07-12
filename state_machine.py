from dataclasses import dataclass
from typing import List, Dict

@dataclass
class State:
    name: str
    cycle: str | List[str]
    next_state: str | List[str|tuple] | Dict[str, str]

    def __post_init__(self):
        if not isinstance(self.cycle, list):
            assert isinstance(self.cycle, str)
            self.cycle = [self.cycle]
        if not isinstance(self.next_state, dict):            
            if not isinstance(self.next_state, list):
                assert isinstance(self.next_state, str)
                self.next_state = [self.next_state]
            res = {}
            for v in self.next_state:
                if isinstance(v, tuple):
                    assert len(v) == 2
                    res[v[0]] = v[1]
                else:
                    assert isinstance(v, str)
                    res[v]=v            
            self.next_state = res

            for st in self.next_state.keys():
                if st == self.name:
                    raise ValueError(f"State '{st}' can't be next for itself")
                elif st in self.cycle:
                    raise ValueError(f"State '{st}' can't be next - it is in .cycle")

def log(s):
#    print(s)
    pass

class StateMachine:
    def __init__(self, states = List[State], init_state: str = None, event_handler = None):
        if not states:
            raise ValueError('Expected at less one state')
        
        self._states = {st.name:st for st in states}
        
        if not init_state:
            init_state = states[0].name
        assert init_state in self._states
        
        self.state = self._states[init_state]
        self.prev_state = None

        self.last_signal = None
        self.last_data = None

        self.receiver = event_handler

    def add_state(name, cycle, next_state):
        self._states[name] = State(name, cycle, next_state)

    def signal(self, signal: str, data = None):
        log(f"StateMachine:: signal({signal}) state={self.state.name}")
        self.last_signal = signal
        self.last_data = data
        
        if signal in self.state.cycle:
            self._callback('cycle')
            return
        elif signal in self.state.next_state:            
            next_state = self.state.next_state[signal]
            self.set_state(next_state)
        else:
            resolved = self._callback('fail')
            if not resolved: 
                raise WrongSignalException(f"Can't process signal '{signal}' at state {self.state}")
            
    def set_state(self, new_state, run_callbacks=True):
        assert new_state in self._states
        log(f"StateMachine:: set_state('{new_state}') signal {self.last_signal}")

        if new_state == self.state.name:
            log('StateMachine:: set_state fail because SAME')
            return False

        if run_callbacks:
            cancel = self._callback('exit')
            if cancel:
                log('StateMachine:: set_state fail because CANCEL')
                return False
            
        self.prev_state = self.state
        self.state = self._states[new_state]

        if run_callbacks:
            self._callback('enter')

        return True

    def _callback(self, event):
        """
        event types: enter cycle exit fail
        """
        if not self.receiver:
            return
        
        # any state handler
        callback1 = getattr(self.receiver, 'on_' + event + '_state', None)
        # exact state handler
        callback_name = 'on_' + self.state.name + '_' + event
        callback2 = getattr(self.receiver, callback_name, None)
        res = False
        for f in (callback1, callback2):
            if f:
                res = res or f(self.last_signal, self.last_data, self)
        return res
        
class WrongSignalException(Exception): pass
