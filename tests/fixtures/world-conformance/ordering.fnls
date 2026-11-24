world Ordering {
  entity Log {
    state sum: int = 0;
    event Mark(digit: int);
    rule Trigger on event Trigger { emit Mark(digit = 4) after 0; }
    rule Add on event Mark { transition sum = sum + payload.digit; }
  }
}
