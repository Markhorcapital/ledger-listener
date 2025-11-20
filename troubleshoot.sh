#!/bin/bash
# MongoDB Connection Troubleshooting Script

echo "=== MongoDB Connection Troubleshooting ==="
echo ""

echo "1. Testing MongoDB port from HOST (not Docker):"
timeout 5 bash -c 'cat < /dev/null > /dev/tcp/13.214.150.182/27017' && echo "✅ Port 27017 is OPEN from host" || echo "❌ Port 27017 is CLOSED/BLOCKED from host"
echo ""

echo "2. Your server's PRIVATE IP (what MongoDB sees):"
hostname -I | awk '{print $1}'
echo ""

echo "3. Your server's PUBLIC IP:"
curl -s ifconfig.me
echo ""
echo ""

echo "4. Testing with Python from HOST:"
python3 -c "import socket; s=socket.socket(); s.settimeout(5); result=s.connect_ex(('13.214.150.182', 27017)); print('✅ Port OPEN from Python' if result==0 else '❌ Port CLOSED from Python'); s.close()"
echo ""

echo "5. Checking if other project's MongoDB connection:"
ps aux | grep -i mongo | grep -v grep || echo "No MongoDB processes found"
echo ""

echo "6. Testing MongoDB connection with mongosh (if installed):"
mongosh "mongodb://dashboard:Markhor%40D3fault@13.214.150.182:27017/?authSource=admin" --eval "db.adminCommand('ping')" 2>&1 | head -5 || echo "mongosh not installed or connection failed"
echo ""

echo "=== Next Steps ==="
echo "If port is CLOSED from host:"
echo "  → You need to whitelist your PRIVATE IP in MongoDB Security Group"
echo ""
echo "If port is OPEN from host but Docker can't connect:"
echo "  → Check Docker network configuration"
echo ""
echo "Your PRIVATE IP should be whitelisted in MongoDB Security Group at 13.214.150.182"

