world Recursion {
  entity Counter {
    state value: int = 0;
    rule Repeat on event Tick {
      transition value = value + 1;
      emit Tick after 0;
    }
  }
}
