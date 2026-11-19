"""Optional bounded UART history, separate from valid peripheral TX admission."""
import hashlib
from pathlib import Path

BASE_SHA = '07f366fd78b099c6247a714f028cee43b4a996e6254c7918233ef9fec31a7fe5'


def component():
    source = Path(__file__).with_name('renode-strict-mmio.cs').read_text()
    start = '    public sealed class BlackwallUartAdapter : IPeripheral\n'
    end = '    public sealed class BlackwallAdcPower\n'
    old = start + source.split(start, 1)[1].split(end, 1)[0]
    if hashlib.sha256(old.encode()).hexdigest() != BASE_SHA:
        raise ValueError('Changed UART adapter baseline')
    new = old

    def change(before, after):
        nonlocal new
        if new.count(before) != 1:
            raise ValueError('Unknown UART history boundary: ' + before[:60])
        new = new.replace(before, after, 1)

    change('bool receiveTimeout=false)', 'bool receiveTimeout=false,bool boundedTxCapture=false)')
    change('            ReceiveFifo=receiveFifo;', '            BoundedTxCapture=boundedTxCapture;\n            ReceiveFifo=receiveFifo;')
    change('TxBytes.Add(b); if(InterruptsEnabled)',
           'TxBytesTotal++;TxBytesHash=unchecked((TxBytesHash^b)*1099511628211ul);if(!BoundedTxCapture || TxBytes.Count<4096)TxBytes.Add(b); if(InterruptsEnabled)')
    change('TxBytes.Clear(); Reads=Writes=', 'TxBytes.Clear();TxBytesTotal=0;TxBytesHash=14695981039346656037ul; Reads=Writes=')
    change('|| TxBytes.Count>=4096)', '|| (!BoundedTxCapture && TxBytes.Count>=4096))')
    change('count<=4095 && TxBytes.Count+count<=4096 &&', 'count<=4095 && (BoundedTxCapture || TxBytes.Count+count<=4096) &&')
    change('        public System.Collections.Generic.List<byte> TxBytes { get; }',
           '''        public bool BoundedTxCapture {get;}
        public ulong TxBytesTotal {get;private set;}
        public ulong TxBytesHash {get;private set;}
        public ulong TxBytesDropped => TxBytesTotal-(ulong)TxBytes.Count;
        public bool TxHistoryTruncated => TxBytesDropped!=0;
        public System.Collections.Generic.List<byte> TxBytes { get; }''')
    return old, new
