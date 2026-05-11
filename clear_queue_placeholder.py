import requests
import json

# Configuration
API_URL = "https://api.paperdrop.me"
DEVICE_ID = "PD-780420ea" # Use the device code for now, but backend expects UUID? 
# Wait, the clearQueue implementation expects deviceId in body.
# And it uses prisma.message.deleteMany({ where: { deviceId: String(deviceId) } })
# The deviceId in the message table is likely the UUID, not the code.
# But let's try sending the code first, or we might need to look up the UUID.
# Actually, looking at the database schema, Device.id is UUID. Device.deviceCode is the code.
# Message.deviceId references Device.id.
# So we MUST send the UUID.

# Let's try to fetch the device UUID first using the code?
# Or we can just ask the user to provide it if they know it.
# But wait, the user probably doesn't know the UUID.
# The frontend uses the UUID.
# Let's try to fetch the device details first? No public endpoint for that.
# However, the agent logs show "Device connected: PD-780420ea (UUID)".
# Let's check the logs again to find the UUID.

# From previous logs: "Device connected: PD-780420ea (UUID)" was not explicitly shown with UUID.
# But wait, the agent sends "device_hello".
# The backend logs "Device connected: ...".

# Let's assume for a moment we need the UUID.
# I will create a script that tries to clear it, but I need the UUID.
# I can get the UUID from the database if I had access, but I don't.
# I can get it from the frontend network tab if I were the user.

# Alternative: I can update the clearQueue endpoint to accept deviceCode and look it up!
# That would be much more user friendly.

# Let's update the backend to support deviceCode lookup in clearQueue.
pass
