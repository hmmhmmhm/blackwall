"""Original sleep return -> fresh original service initialization and virtual phone time action."""
POST='''
try:
    if not original_sleep_return.Seen or not m.IsPaused:raise ValueError('Need original sleep caller return')
    original_sleep_return.Detach()
    reboot_hold=BlackwallUiActivationHold(m,cpu,p['getter'])
    restart_start=int(m.ElapsedVirtualTime.TimeElapsed.Ticks);restart_deadline=time.time()+90
    reset_emulation.StartAll()
    while not m.IsPaused and time.time()<restart_deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-restart_start<10000000000:time.sleep(0.005)
    m.Pause();restart=reset_state();restart['held']=bool(reboot_hold.Held)
    restart['guard_detail']=[dict(name=x['name'],accesses=int(m['sysbus.'+x['name']].AccessCount),address=int(m['sysbus.'+x['name']].LastAddress),width=int(m['sysbus.'+x['name']].LastWidth),value=int(m['sysbus.'+x['name']].LastValue),operation=str(m['sysbus.'+x['name']].LastOperation)) for x in result['guards']]
    restart['sleep_events']=[[int(x) for x in row] for row in sleep_transition.Events];restart['sleep_overflow']=bool(sleep_transition.Overflow)
    File.WriteAllBytes('/work-output/restart-service-sram.bin',b.ReadBytes(0x20000000,0x380000,True));File.WriteAllText('/work-output/restart-service.json',json.dumps(restart));Console.WriteLine('BLACKWALL_RESTART_SERVICE '+json.dumps(restart))
    if not reboot_hold.Held or any(x['accesses'] for x in restart['guards']) or restart['cfsr'] or restart['hfsr'] or restart['memory']['violations']:raise ValueError('Original services did not restart cleanly')
    new_connection=BlackwallRuntimeConnectionObserver(m,cpu,p['gpio']['isr'],p['opened'],p['finished'],p['tcb_slot'])
    c=p['service'];new_app=BlackwallTplServiceObserver(m,cpu,c['ingress'],c['consumer'],c['clock_return'],c['consumer_return'],p['tcb_slot'])
    accepted=bool(peer.TryQueueRuntimeConnection())
    if not accepted:raise ValueError('Fresh virtual connection preconditions rejected')
    restart_start=int(m.ElapsedVirtualTime.TimeElapsed.Ticks);restart_deadline=time.time()+30
    reset_emulation.StartAll()
    while not m.IsPaused and time.time()<restart_deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-restart_start<1000000000:time.sleep(0.001)
    m.Pause();reconnected=reset_state();reconnected.update(accepted=accepted,stopped=bool(new_connection.Stopped),entry=[int(x) for x in new_connection.Entry],exit=[int(x) for x in new_connection.Exit])
    File.WriteAllText('/work-output/restart-connection.json',json.dumps(reconnected));Console.WriteLine('BLACKWALL_RESTART_CONNECTION '+json.dumps(reconnected))
    if not new_connection.Stopped:raise ValueError('Original connection handler did not return')
    restart_start=int(m.ElapsedVirtualTime.TimeElapsed.Ticks);restart_deadline=time.time()+30
    reset_emulation.StartAll()
    while not m.IsPaused and time.time()<restart_deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-restart_start<1000000000:time.sleep(0.001)
    m.Pause();reapplied=reset_state();reapplied.update(stopped=bool(new_app.Stopped),inputs=[[int(x) for x in row] for row in new_app.Inputs],consumers=[[int(x) for x in row] for row in new_app.Consumers],applied=[[int(x) for x in row] for row in new_app.Applied],returns=[[int(x) for x in row] for row in new_app.Returns])
    File.WriteAllBytes('/work-output/restart-app-sram.bin',b.ReadBytes(0x20000000,0x380000,True));File.WriteAllText('/work-output/restart-app.json',json.dumps(reapplied));Console.WriteLine('BLACKWALL_RESTART_APP '+json.dumps(reapplied))
except Exception as error:Console.WriteLine('BLACKWALL_RESTART_APP_ERROR '+str(error))
'''
