type BluetoothServiceUUID = string | number;
type BluetoothCharacteristicUUID = string | number;

interface BluetoothLEScanFilter {
    name?: string;
    namePrefix?: string;
    services?: BluetoothServiceUUID[];
}

interface RequestDeviceOptions {
    filters?: BluetoothLEScanFilter[];
    optionalServices?: BluetoothServiceUUID[];
}

interface BluetoothRemoteGATTCharacteristic extends EventTarget {
    readValue(): Promise<DataView>;
    writeValue(value: BufferSource): Promise<void>;
    startNotifications(): Promise<BluetoothRemoteGATTCharacteristic>;
    addEventListener(
        type: 'characteristicvaluechanged',
        listener: (event: Event) => void,
        options?: boolean | AddEventListenerOptions
    ): void;
}

interface BluetoothRemoteGATTService {
    getCharacteristic(
        characteristic: BluetoothCharacteristicUUID
    ): Promise<BluetoothRemoteGATTCharacteristic>;
}

interface BluetoothRemoteGATTServer {
    connected: boolean;
    connect(): Promise<BluetoothRemoteGATTServer>;
    disconnect(): void;
    getPrimaryService(service: BluetoothServiceUUID): Promise<BluetoothRemoteGATTService>;
}

interface BluetoothDevice {
    name?: string;
    gatt?: BluetoothRemoteGATTServer;
}

interface Bluetooth {
    requestDevice(options?: RequestDeviceOptions): Promise<BluetoothDevice>;
}

interface Navigator {
    bluetooth?: Bluetooth;
}
