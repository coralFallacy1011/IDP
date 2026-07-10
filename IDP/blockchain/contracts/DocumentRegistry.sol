// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract DocumentRegistry {
    struct DocumentRecord {
        string documentId;
        string documentHash;
        uint256 timestamp;
    }

    mapping(string => DocumentRecord) private documents;

    event DocumentRegistered(
        string documentId,
        string documentHash,
        uint256 timestamp
    );

    function registerDocument(
        string memory documentId,
        string memory documentHash
    ) public {

        documents[documentId] =
            DocumentRecord(
                documentId,
                documentHash,
                block.timestamp
            );

        emit DocumentRegistered(
            documentId,
            documentHash,
            block.timestamp
        );
    }

    function verifyDocument(
        string memory documentId,
        string memory documentHash
    )
        public
        view
        returns(bool)
    {
        return keccak256(
            bytes(
                documents[documentId].documentHash
            )
        )
        ==
        keccak256(
            bytes(documentHash)
        );
    }

    function getDocument(
        string memory documentId
    )
        public
        view
        returns(
            string memory,
            string memory,
            uint256
        )
    {
        DocumentRecord memory d =
            documents[documentId];

        return (
            d.documentId,
            d.documentHash,
            d.timestamp
        );
    }
}
