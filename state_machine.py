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


class StateMachine:
    def __init__(self, states = List[State], init_state: str = None, callback_receiver = None):
        if not states:
            raise ValueError('Expected at less one state')
        
        self._states = {st.name:st for st in states}
        
        if not init_state:
            init_state = states[0].name
        assert init_state in self._states
        
        self.state = self._states[init_state]

        self.receiver = callback_receiver

    def add_state(name, cycle, next_state):
        self._states[name] = State(name, cycle, next_state)

    def signal(self, signal: str, data = None):        
        if signal in self.state.cycle:
            self._callback('cycle', signal, data)
            return
        elif signal in self.state.next_state:            
            next_state = self.state.next_state[signal]
            self._set_state(next_state, signal, data)
        else:
            repaired_state = self._callback('fail', signal, data)
            if not repaired_state: 
                raise ValueError(f"Can't process {signal} at state {self.state}")
            else:
                self._set_state(repaired_state, signal, data)

    def _set_state(self, new_state, signal: str, data):
        assert new_state in self._states
        self._callback('exit', signal, data)
        self.state = self._states[new_state]
        self._callback('enter', signal, data)

    def _callback(self, event, signal: str, data):
        if not self.receiver:
            return
        callback_name = 'on_' + self.state.name + '_' + event
        callback = getattr(self.receiver, callback_name, None)
        if callback:
            callback(signal, data, self)
        
        
