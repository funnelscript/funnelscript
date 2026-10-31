// Minimal language-core example: no marketing template or live provider.
world CounterDemo {
  entity Counter {
    state count: int = 0;
    state active: bool = true;

    rule Increment on event Pulse {
      transition count = count + 1;
    }

    rule Stop on event Halt {
      transition active = false;
    }
  }
}
