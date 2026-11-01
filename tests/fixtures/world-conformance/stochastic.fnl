world Sampling {
  agent A {
    state enabled: bool = false;
    state first: float = 0.0;
    state second: bool = true;
    state count: int = 0;
    rule Skip on event Skip when (enabled == true) {
      transition first = sample uniform(0.0, 1.0);
      emit Tick after 0;
    }
    rule Tick on event Tick {
      transition count = count + 1;
      transition first = sample uniform(0.0, 1.0);
      transition second = sample bernoulli(0.5);
    }
  }
}
