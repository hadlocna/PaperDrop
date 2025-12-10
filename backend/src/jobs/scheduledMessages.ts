import { prisma } from '../lib/prisma';
import { broadcastToDevice } from '../websocket/deviceHandler';

class ScheduledMessageProcessor {
    private intervalId: NodeJS.Timeout | null = null;

    start() {
        // Run every minute
        this.intervalId = setInterval(() => this.process(), 60 * 1000);
        console.log('Scheduled message processor started');
    }

    stop() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
    }

    async process() {
        try {
            // Find messages due for delivery that are still queued
            const dueMessages = await prisma.message.findMany({
                where: {
                    status: 'queued',
                    scheduledAt: {
                        lte: new Date(),
                        not: null
                    },
                },
                include: {
                    sender: { select: { name: true } }
                }
            });

            for (const message of dueMessages) {
                // Attempt delivery
                const payload = {
                    type: 'print_job',
                    message_id: message.id,
                    content_type: message.contentType,
                    content: JSON.parse(message.content), // Assuming JSON string in DB
                    sender_name: message.sender.name
                };

                const success = broadcastToDevice(message.deviceId, payload);

                if (success) {
                    await prisma.message.update({
                        where: { id: message.id },
                        data: { status: 'sent', sentAt: new Date() }
                    });
                }
                // If offline, it stays queued (but scheduledAt is in past, so it will be picked up again?
                // No, we should probably check if device is online before picking?
                // Or relies on 'deliverQueuedMessages' on reconnect.
                // Ideally we don't want to loop failing every minute if device is offline.
                // But broadcastToDevice returns fail if offline. So no harm done except some cycles.
            }

            if (dueMessages.length > 0) {
                console.log(`Processed ${dueMessages.length} scheduled messages`);
            }
        } catch (error) {
            console.error('Error processing scheduled messages:', error);
        }
    }
}

export const scheduledMessageProcessor = new ScheduledMessageProcessor();
