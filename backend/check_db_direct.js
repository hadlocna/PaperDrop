const { Client } = require('pg');

async function main() {
    const client = new Client({
        connectionString: 'postgresql://nathanhadlock@localhost:5432/postgres'
    });

    try {
        await client.connect();
        const res = await client.query('SELECT * FROM devices WHERE "deviceCode" = $1', ['PD-780420ea']);
        if (res.rows.length > 0) {
            console.log('Device found in DB:');
            console.log(JSON.stringify(res.rows[0], null, 2));
        } else {
            console.log('Device not found in DB');
        }
    } catch (err) {
        console.error('Error querying DB:', err);
    } finally {
        await client.end();
    }
}

main();
