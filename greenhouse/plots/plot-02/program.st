PROGRAM lettuce_plot_02
  VAR
    lamps_cmd AT %QX0.0 : BOOL;
    heat_cmd AT %QX0.1 : BOOL;
    water_cmd AT %QX0.2 : BOOL;
    lamps_running AT %IX0.0 : BOOL;
    heat_running AT %IX0.1 : BOOL;
    water_running AT %IX0.2 : BOOL;
    temp_raw AT %IW0 : INT;
    moisture_raw AT %IW1 : INT;
    events_raw AT %IW2 : INT;
    temp_sp_raw AT %QW0 : INT;
    moisture_sp_raw AT %QW1 : INT;
  END_VAR

  VAR
    temp_sim : REAL := 15.0;
    moist_sim : REAL := 75.0;
    cycles : INT := 0;
    events : INT := 0;
    water_prev : BOOL := FALSE;
  END_VAR

  lamps_running := lamps_cmd;
  heat_running := heat_cmd;
  water_running := water_cmd;

  cycles := cycles + 1;
  IF cycles >= 50 THEN
    cycles := 0;
  END_IF;

  IF water_cmd THEN
    moist_sim := moist_sim + 0.08;
    IF moist_sim > 90.0 THEN
      moist_sim := 90.0;
    END_IF;
  ELSE
    moist_sim := moist_sim - 0.02;
    IF moist_sim < 50.0 THEN
      moist_sim := 50.0;
    END_IF;
  END_IF;

  IF heat_cmd THEN
    temp_sim := temp_sim + 0.03;
    IF temp_sim > 25.0 THEN
      temp_sim := 25.0;
    END_IF;
  ELSE
    temp_sim := temp_sim - 0.01;
    IF temp_sim < 10.0 THEN
      temp_sim := 10.0;
    END_IF;
  END_IF;

  IF water_cmd AND NOT water_prev THEN
    events := events + 1;
  END_IF;
  water_prev := water_cmd;

  temp_raw := REAL_TO_INT(temp_sim * 10.0);
  moisture_raw := REAL_TO_INT(moist_sim);
  events_raw := events;
  temp_sp_raw := 190;
  moisture_sp_raw := 70;
END_PROGRAM

CONFIGURATION Config0

  RESOURCE Res0 ON PLC
    TASK task0(INTERVAL := T#20ms,PRIORITY := 0);
    PROGRAM instance0 WITH task0 : lettuce_plot_02;
  END_RESOURCE
END_CONFIGURATION
