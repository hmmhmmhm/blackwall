"""Attach only the explicitly selected MSPI1 power domain, leaving all bus MMIO strict."""
def attach(board,profile):
 if profile not in (None,'active','stuck-off'):raise ValueError('Explicit MSPI1 power profile required')
 needle='    baseAddress: 0x40001000\n'
 if board.count(needle)!=1 or 'mspi1_power:' in board:raise ValueError('Unexpected shared power owner')
 if profile is None:return board
 return board.replace(needle,needle+'    mspi1Power: mspi1_power\n')+'\nmspi1_power: Miscellaneous.BlackwallPeripheralPower @ none\n    mask: 0x8000\n    profile: '+str(int(profile=='active'))+'\n'
