world PopulationOrderBoundary {
  agent A {
    state draw: float = 0.0;
    rule React on event Tick {
      transition draw = sample uniform(0.0, 1.0);
    }
  }
  agent B {
    state draw: float = 0.0;
    rule React on event Tick {
      transition draw = sample uniform(0.0, 1.0);
    }
  }
}
