world PopulationTest {
  agent Visitor {
    state phase: string = "new";
    state draw: float = 0.0;
    rule TickRule on event Tick {
      transition phase = "terminal";
      transition draw = sample uniform(0.0, 1.0);
    }
    rule DeactivateRule on event Deactivate {
      transition phase = "inactive";
    }
  }
}
