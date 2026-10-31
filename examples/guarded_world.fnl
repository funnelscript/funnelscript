// Guarded event chain terminates when value reaches three.
world BoundedFlow {
  agent Counter {
    state value: int = 0;

    rule Advance on event Tick when (value < 3) {
      transition value = value + 1;
      emit Tick after 1;
    }
  }
}
