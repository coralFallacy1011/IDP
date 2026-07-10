"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Shield, CheckCircle2, AlertTriangle, Loader2, Search, Hash, FileText, ExternalLink,
  Workflow, Cpu, Database, Network, Link2, RefreshCw, Layers, ArrowRight
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { verifyDocumentOnChain, getBlockchainRecord, type VerifyResult, type BlockchainRecord } from "@/lib/api";

export default function BlockchainPage() {
  const [verifyDocId, setVerifyDocId] = useState("");
  const [lookupDocId, setLookupDocId] = useState("");
  const [verifying, setVerifying] = useState(false);
  const [looking, setLooking] = useState(false);
  const [verifyResult, setVerifyResult] = useState<VerifyResult | null>(null);
  const [record, setRecord] = useState<BlockchainRecord | null>(null);
  const [verifyError, setVerifyError] = useState<string | null>(null);
  const [lookupError, setLookupError] = useState<string | null>(null);

  // Simulation State
  const [simStep, setSimStep] = useState(0);
  const [simLogs, setSimLogs] = useState<string[]>([]);
  const [simDocName, setSimDocName] = useState("Contract_Draft_07.docx");

  const startSimulation = () => {
    setSimStep(1);
    setSimLogs(["[1/5] Reading file data and initializing hashing..."]);
    
    setTimeout(() => {
      setSimStep(2);
      setSimLogs(prev => [...prev, "[2/5] Generated SHA-256 fingerprint: a9f4c39c81...8f02eb"]);
    }, 1500);

    setTimeout(() => {
      setSimStep(3);
      setSimLogs(prev => [...prev, "[3/5] Broadcasting transaction payload to Smart Contract 'DocumentRegistry' at 0x9fE4..."]);
    }, 3000);

    setTimeout(() => {
      setSimStep(4);
      setSimLogs(prev => [...prev, "[4/5] Transaction included in memory pool. Local hardhat miner validating..."]);
    }, 4500);

    setTimeout(() => {
      setSimStep(5);
      setSimLogs(prev => [...prev, "[5/5] Success! New block added to ledger. Document integrity verified and immutable."]);
    }, 6000);
  };

  const resetSimulation = () => {
    setSimStep(0);
    setSimLogs([]);
  };

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setVerifying(true);
    setVerifyResult(null);
    setVerifyError(null);
    try {
      const res = await verifyDocumentOnChain(verifyDocId.trim());
      setVerifyResult(res);
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 404) setVerifyError("Document not found in database.");
      else if (status === 401) setVerifyError("Authentication required. Please log in.");
      else setVerifyError("Verification failed. Check the document ID and try again.");
    } finally {
      setVerifying(false);
    }
  };

  const handleLookup = async (e: React.FormEvent) => {
    e.preventDefault();
    setLooking(true);
    setRecord(null);
    setLookupError(null);
    try {
      const res = await getBlockchainRecord(lookupDocId.trim());
      setRecord(res);
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 404) setLookupError("No blockchain record found for this document ID.");
      else if (status === 401) setLookupError("Authentication required. Please log in.");
      else setLookupError("Lookup failed. Check the document ID.");
    } finally {
      setLooking(false);
    }
  };

  const blocks = [
    {
      index: 0,
      name: "Genesis Block",
      hash: "0x0000000000000000000000000000000000000000000000000000000000000000",
      prevHash: "0x0000000000000000000000000000000000000000000000000000000000000000",
      txCount: 0,
      timestamp: "System Init",
    },
    {
      index: 1,
      name: "Block #1",
      hash: "0x4e7c377c8e22b07e78d91f2c25608d3df242c16113b2c15928d3efca3c41551a",
      prevHash: "0x0000000000000000000000000000000000000000000000000000000000000000",
      txCount: 1,
      timestamp: "10 mins ago",
    },
    {
      index: 2,
      name: "Block #2",
      hash: "0x789bfa89256cf78112d7c58d0421da63bf21516e87fbc265e1281cb9f2a93110",
      prevHash: "0x4e7c377c8e22b07e78d91f2c25608d3df242c16113b2c15928d3efca3c41551a",
      txCount: 1,
      timestamp: "Just now",
    }
  ];

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Shield className="h-6 w-6 text-blue-600" />
          Blockchain Verification
        </h1>
        <p className="text-muted-foreground text-sm mt-1">
          Verify document integrity, view immutable records, and visualize blockchain transaction flow.
        </p>
      </motion.div>

      <Tabs defaultValue="verify">
        <TabsList className="grid w-full max-w-lg grid-cols-3">
          <TabsTrigger value="verify">Verify Document</TabsTrigger>
          <TabsTrigger value="lookup">Lookup Record</TabsTrigger>
          <TabsTrigger value="visualize">How It Works</TabsTrigger>
        </TabsList>

        {/* ── Verify Tab ── */}
        <TabsContent value="verify" className="mt-4">
          <div className="grid lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-blue-600" />
                  Verify Document Integrity
                </CardTitle>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleVerify} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="verify-id">Document ID (MongoDB ObjectId)</Label>
                    <Input
                      id="verify-id"
                      value={verifyDocId}
                      onChange={(e) => setVerifyDocId(e.target.value)}
                      placeholder="e.g. 64a1b2c3d4e5f6789012abcd"
                      className="font-mono text-sm"
                      required
                    />
                    <p className="text-xs text-muted-foreground">
                      The document ID returned when you uploaded via OCR scan.
                    </p>
                  </div>
                  <Button type="submit" disabled={verifying} className="w-full gap-2">
                    {verifying ? (
                      <><Loader2 className="h-4 w-4 animate-spin" /> Verifying...</>
                    ) : (
                      <><Search className="h-4 w-4" /> Verify on Blockchain</>
                    )}
                  </Button>
                </form>

                {verifyError && (
                  <div className="mt-4 flex items-start gap-2 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
                    <AlertTriangle className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
                    <p className="text-xs text-red-700 dark:text-red-400">{verifyError}</p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Verify result */}
            {verifyResult && (
              <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}>
                <Card className={verifyResult.status === "authentic"
                  ? "border-emerald-200 dark:border-emerald-800 bg-emerald-50/50 dark:bg-emerald-900/10"
                  : "border-red-200 dark:border-red-800 bg-red-50/50 dark:bg-red-900/10"}>
                  <CardHeader>
                    <CardTitle className="text-sm flex items-center gap-2">
                      {verifyResult.status === "authentic" ? (
                        <><CheckCircle2 className="h-4 w-4 text-emerald-600" /> Document Authentic</>
                      ) : (
                        <><AlertTriangle className="h-4 w-4 text-red-600" /> Document Tampered</>
                      )}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3 text-xs">
                    <div className="flex items-center gap-2">
                      <span className="text-muted-foreground">Status:</span>
                      <Badge variant={verifyResult.status === "authentic" ? "success" : "destructive"}>
                        {verifyResult.status.toUpperCase()}
                      </Badge>
                    </div>
                    <div>
                      <p className="text-muted-foreground mb-1">Document ID</p>
                      <p className="font-mono break-all">{verifyResult.document_id}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground mb-1">Document Hash (SHA-256)</p>
                      <p className="font-mono break-all text-xs bg-muted/50 p-2 rounded">
                        {verifyResult.document_hash}
                      </p>
                    </div>
                    {verifyResult.status === "authentic" ? (
                      <p className="text-emerald-700 dark:text-emerald-400">
                        ✓ Hash matches on-chain record. Document has not been modified.
                      </p>
                    ) : (
                      <p className="text-red-700 dark:text-red-400">
                        ✗ Hash does not match on-chain record. Document may have been tampered.
                      </p>
                    )}
                  </CardContent>
                </Card>
              </motion.div>
            )}
          </div>
        </TabsContent>

        {/* ── Lookup Tab ── */}
        <TabsContent value="lookup" className="mt-4">
          <div className="grid lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm flex items-center gap-2">
                  <Hash className="h-4 w-4 text-blue-600" />
                  Lookup Blockchain Record
                </CardTitle>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleLookup} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="lookup-id">Document ID</Label>
                    <Input
                      id="lookup-id"
                      value={lookupDocId}
                      onChange={(e) => setLookupDocId(e.target.value)}
                      placeholder="e.g. 64a1b2c3d4e5f6789012abcd"
                      className="font-mono text-sm"
                      required
                    />
                  </div>
                  <Button type="submit" disabled={looking} className="w-full gap-2">
                    {looking ? (
                      <><Loader2 className="h-4 w-4 animate-spin" /> Looking up...</>
                    ) : (
                      <><Search className="h-4 w-4" /> Fetch Record</>
                    )}
                  </Button>
                </form>

                {lookupError && (
                  <div className="mt-4 flex items-start gap-2 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
                    <AlertTriangle className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
                    <p className="text-xs text-red-700 dark:text-red-400">{lookupError}</p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Record result */}
            {record && (
              <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}>
                <Card className="border-blue-200 dark:border-blue-800">
                  <CardHeader>
                    <CardTitle className="text-sm flex items-center gap-2">
                      <FileText className="h-4 w-4 text-blue-600" /> On-Chain Record
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3 text-xs">
                    <div className="grid grid-cols-2 gap-2">
                      <div className="p-2 rounded-lg bg-muted/50 border">
                        <p className="text-muted-foreground">Registered</p>
                        <p className="font-medium mt-0.5">{record.registered ? "Yes ✓" : "No"}</p>
                      </div>
                      {record.block_number && (
                        <div className="p-2 rounded-lg bg-muted/50 border">
                          <p className="text-muted-foreground">Block Number</p>
                          <p className="font-medium mt-0.5">#{record.block_number}</p>
                        </div>
                      )}
                    </div>
                    <div>
                      <p className="text-muted-foreground mb-1">Document Hash</p>
                      <p className="font-mono break-all bg-muted/50 p-2 rounded text-xs">
                        {record.document_hash}
                      </p>
                    </div>
                    {record.transaction_hash && (
                      <div>
                        <p className="text-muted-foreground mb-1 flex items-center gap-1">
                          Transaction Hash <ExternalLink className="h-3 w-3" />
                        </p>
                        <p className="font-mono break-all bg-muted/50 p-2 rounded text-xs">
                          {record.transaction_hash}
                        </p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </motion.div>
            )}
          </div>
        </TabsContent>

        {/* ── Visualize/How it Works Tab ── */}
        <TabsContent value="visualize" className="mt-4">
          <div className="grid lg:grid-cols-3 gap-6">
            {/* Simulation Controller */}
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="text-sm flex items-center gap-2">
                  <Workflow className="h-4 w-4 text-blue-600" /> Document Anchoring flow Visualizer
                </CardTitle>
                <p className="text-xs text-muted-foreground mt-1">
                  Interact with the flowchart below to witness the automated cryptographic steps deployed on our local Hardhat Blockchain ledger.
                </p>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="flex flex-wrap gap-3 items-center justify-between bg-muted/40 p-4 rounded-xl border">
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">File to anchor</Label>
                    <Input 
                      value={simDocName} 
                      onChange={(e) => setSimDocName(e.target.value)} 
                      className="h-8 text-xs font-semibold w-56 bg-background"
                      disabled={simStep > 0 && simStep < 5}
                    />
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" onClick={startSimulation} disabled={simStep > 0} className="gap-2">
                      <RefreshCw className={`h-3.5 w-3.5 ${simStep > 0 && simStep < 5 ? "animate-spin" : ""}`} />
                      Start Workflow
                    </Button>
                    <Button size="sm" variant="outline" onClick={resetSimulation} disabled={simStep === 0}>
                      Reset
                    </Button>
                  </div>
                </div>

                {/* Animated Pipeline Nodes */}
                <div className="grid grid-cols-1 md:grid-cols-5 gap-3 items-center relative py-4">
                  {[
                    { step: 1, label: "1. Upload File", icon: FileText, desc: "Extracting legal metadata & OCR clean texts" },
                    { step: 2, label: "2. Hash (SHA-256)", icon: Cpu, desc: "Compute unique math signature of file contents" },
                    { step: 3, label: "3. Smart Contract", icon: Shield, desc: "Invoke registerDocument transaction" },
                    { step: 4, label: "4. Mine block", icon: Layers, desc: "Hardhat consensus mines block with txHash" },
                    { step: 5, label: "5. Immutable Chain", icon: CheckCircle2, desc: "Hash recorded on-chain forever" }
                  ].map((node, i) => {
                    const isActive = simStep >= node.step;
                    const isProcessing = simStep === node.step;
                    return (
                      <div key={i} className="flex flex-col items-center text-center space-y-2 relative">
                        <motion.div
                          animate={isProcessing ? { scale: [1, 1.12, 1] } : {}}
                          transition={{ repeat: Infinity, duration: 1.5 }}
                          className={`h-12 w-12 rounded-full border-2 flex items-center justify-center transition-all ${
                            isActive
                              ? "bg-blue-600 border-blue-700 text-white shadow-md shadow-blue-500/20"
                              : "bg-muted border-border text-muted-foreground"
                          }`}
                        >
                          <node.icon className="h-5 w-5" />
                        </motion.div>
                        <div>
                          <p className="text-xs font-bold">{node.label}</p>
                          <p className="text-[10px] text-muted-foreground max-w-[120px] mx-auto mt-1 leading-normal">
                            {node.desc}
                          </p>
                        </div>
                        {i < 4 && (
                          <div className="hidden md:block absolute top-6 -right-4 translate-x-1/2 z-10 text-muted-foreground">
                            <ArrowRight className="h-4 w-4" />
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* Simulated Logs */}
                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 font-mono text-xs text-slate-400 space-y-1.5 h-36 overflow-y-auto">
                  <p className="text-blue-500 font-bold">--- FLOW SIMULATION CONSOLE ---</p>
                  {simLogs.map((log, index) => (
                    <motion.p initial={{ opacity: 0, x: -5 }} animate={{ opacity: 1, x: 0 }} key={index}>
                      {log}
                    </motion.p>
                  ))}
                  {simStep === 0 && <p className="text-slate-600">Click 'Start Workflow' to observe the cryptographic pipeline...</p>}
                </div>
              </CardContent>
            </Card>

            {/* Block Ledger Explorer */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm flex items-center gap-2">
                  <Database className="h-4 w-4 text-purple-600" /> Block Ledger Explorer
                </CardTitle>
                <p className="text-xs text-muted-foreground mt-1">
                  How blocks are linked using `previousHash` references.
                </p>
              </CardHeader>
              <CardContent className="space-y-4">
                {blocks.map((block, idx) => (
                  <div key={idx} className="relative">
                    <Card className="border border-border bg-muted/30">
                      <CardContent className="p-3 space-y-2 text-[10px]">
                        <div className="flex items-center justify-between border-b pb-1.5 mb-1.5">
                          <span className="font-bold text-xs text-blue-600 dark:text-blue-400">{block.name}</span>
                          <Badge variant="outline" className="text-[9px] px-1 py-0">{block.timestamp}</Badge>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Block Hash:</span>
                          <p className="font-mono text-foreground font-semibold truncate" title={block.hash}>
                            {block.hash}
                          </p>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Previous Hash:</span>
                          <p className="font-mono text-slate-400 truncate" title={block.prevHash}>
                            {block.prevHash}
                          </p>
                        </div>
                        <div className="flex justify-between items-center text-[9px] pt-1 text-muted-foreground">
                          <span>Transactions: {block.txCount}</span>
                          <span className="flex items-center gap-0.5 text-emerald-600"><CheckCircle2 className="h-3 w-3" /> Validated</span>
                        </div>
                      </CardContent>
                    </Card>
                    {idx < blocks.length - 1 && (
                      <div className="flex justify-center my-2 text-blue-500">
                        <Link2 className="h-4 w-4 rotate-90" />
                      </div>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
