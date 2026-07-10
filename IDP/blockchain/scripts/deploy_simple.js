/**
 * Simple deploy script using web3 - no Hardhat ethers plugin needed.
 * Deploys DocumentRegistry contract to the running Hardhat node on port 8545.
 * 
 * Usage: node scripts/deploy_simple.js
 */

const fs = require('fs');
const path = require('path');
const http = require('http');

const RPC_URL = 'http://127.0.0.1:8545';

// Read artifact
const artifactPath = path.join(__dirname, '..', 'DocumentRegistry.abi.json');
const artifact = JSON.parse(fs.readFileSync(artifactPath, 'utf8'));
const abi = artifact.abi;
const bytecode = artifact.bytecode;

function rpcCall(method, params = []) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify({
      jsonrpc: '2.0',
      method,
      params,
      id: Date.now()
    });

    const req = http.request('http://127.0.0.1:8545', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(body)
      }
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        const parsed = JSON.parse(data);
        if (parsed.error) reject(new Error(parsed.error.message));
        else resolve(parsed.result);
      });
    });
    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

async function main() {
  console.log('Connecting to Hardhat node at', RPC_URL, '...');

  // Get accounts
  const accounts = await rpcCall('eth_accounts');
  const deployer = accounts[0];
  console.log('Deployer account:', deployer);

  // Get chain id
  const chainIdHex = await rpcCall('eth_chainId');
  console.log('Chain ID:', parseInt(chainIdHex, 16));

  // Get nonce
  const nonce = await rpcCall('eth_getTransactionCount', [deployer, 'latest']);

  // Estimate gas
  const gasEstimate = await rpcCall('eth_estimateGas', [{
    from: deployer,
    data: bytecode
  }]);
  console.log('Gas estimate:', parseInt(gasEstimate, 16));

  // Send deployment transaction
  const txHash = await rpcCall('eth_sendTransaction', [{
    from: deployer,
    data: bytecode,
    gas: gasEstimate,
    nonce: nonce
  }]);
  console.log('Transaction hash:', txHash);

  // Wait for receipt
  let receipt = null;
  for (let i = 0; i < 30; i++) {
    receipt = await rpcCall('eth_getTransactionReceipt', [txHash]);
    if (receipt) break;
    await new Promise(r => setTimeout(r, 1000));
  }

  if (!receipt) {
    throw new Error('Transaction receipt not found after 30s');
  }

  const contractAddress = receipt.contractAddress;
  console.log('DocumentRegistry deployed to:', contractAddress);

  // Save address
  const baseDir = path.join(__dirname, '..');
  fs.writeFileSync(path.join(baseDir, 'DocumentRegistry.address.txt'), contractAddress);
  console.log('Address saved to DocumentRegistry.address.txt');
}

main().catch(err => {
  console.error('Deploy failed:', err.message);
  process.exit(1);
});
