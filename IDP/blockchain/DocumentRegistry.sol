// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract DocumentRegistry {
    struct DocumentRecord {
        string documentId;
        string documentHash;
        uint256 timestamp;
    }

    mapping(string => DocumentRecord) private records;

    event DocumentRegistered(string indexed documentId, string documentHash, uint256 timestamp);

    function registerDocument(string calldata documentId, string calldata documentHash) external {
        records[documentId] = DocumentRecord(documentId, documentHash, block.timestamp);
        emit DocumentRegistered(documentId, documentHash, block.timestamp);
    }

    function verifyDocument(string calldata documentId, string calldata documentHash) external view returns (bool) {
        DocumentRecord storage rec = records[documentId];
        if (bytes(rec.documentId).length == 0) {
            return false;
        }
        return (keccak256(bytes(rec.documentHash)) == keccak256(bytes(documentHash)));
    }

    // helper to read stored hash
    function getDocumentHash(string calldata documentId) external view returns (string memory) {
        return records[documentId].documentHash;
    }
}
