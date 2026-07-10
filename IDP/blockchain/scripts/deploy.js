const fs = require('fs');
const path = require('path');

async function main() {
  const hre = require('hardhat');
  const DocumentRegistry = await hre.ethers.getContractFactory('DocumentRegistry');
  const doc = await DocumentRegistry.deploy();
  await doc.deployed();
  console.log('DocumentRegistry deployed to:', doc.address);

  const artifactsPath = path.join(__dirname, '..');
  const abi = await hre.artifacts.readArtifact('DocumentRegistry');
  fs.writeFileSync(path.join(artifactsPath, 'DocumentRegistry.abi.json'), JSON.stringify(abi, null, 2));
  fs.writeFileSync(path.join(artifactsPath, 'DocumentRegistry.address.txt'), doc.address);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
