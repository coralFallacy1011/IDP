"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  MessageSquare, Send, FileText, Loader2, Bot, User,
  ChevronDown, Hash, AlertTriangle, Trash2, X,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { chatWithDocument } from "@/lib/api";
import { useAppStore, type ChatMessage } from "@/store/useAppStore";
import { cn, formatDateTime } from "@/lib/utils";

let msgIdCounter = 0;
const genId = () => `msg-${++msgIdCounter}-${Date.now()}`;

export default function ChatPage() {
  const { documents, chatHistory, addChatMessage, getChatHistory, clearChatHistory } = useAppStore();
  const [selectedDocId, setSelectedDocId] = useState<string>("");
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedSources, setExpandedSources] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const messages = selectedDocId ? getChatHistory(selectedDocId) : [];

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const selectedDoc = documents.find((d) => d.id === selectedDocId);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || !selectedDocId || loading) return;

    const userMsg: ChatMessage = {
      id: genId(),
      role: "user",
      content: text,
      timestamp: new Date(),
    };
    addChatMessage(selectedDocId, userMsg);
    setInput("");
    setError(null);
    setLoading(true);

    try {
      const res = await chatWithDocument(selectedDocId, text);
      if (res.ok) {
        const assistantMsg: ChatMessage = {
          id: genId(),
          role: "assistant",
          content: res.data.answer,
          sources: res.data.source_chunks,
          timestamp: new Date(),
        };
        addChatMessage(selectedDocId, assistantMsg);
      }
    } catch {
      setError("Failed to get a response. Make sure the backend + TinyLlama model are available.");
      // Remove the user message optimistically added
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="space-y-4 h-[calc(100vh-7rem)] flex flex-col">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="shrink-0">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <MessageSquare className="h-6 w-6 text-blue-600" /> Legal Chatbot
        </h1>
        <p className="text-muted-foreground text-sm mt-1">
          Ask questions about your documents. Answers are grounded in retrieved text chunks (RAG).
        </p>
      </motion.div>

      <div className="grid lg:grid-cols-4 gap-4 flex-1 min-h-0">
        {/* Sidebar — doc selector */}
        <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}
          className="lg:col-span-1 flex flex-col gap-3">
          <Card className="flex-1">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Document</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {documents.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  No documents. <a href="/dashboard/ocr" className="text-blue-600 underline underline-offset-2">Upload one.</a>
                </p>
              ) : (
                documents.map((d) => (
                  <button
                    key={d.id}
                    onClick={() => setSelectedDocId(d.id === selectedDocId ? "" : d.id)}
                    className={cn(
                      "w-full flex items-center gap-2 p-2 rounded-lg border text-left text-xs transition-all",
                      d.id === selectedDocId
                        ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20"
                        : "border-border hover:bg-muted/50"
                    )}
                  >
                    <FileText className="h-3.5 w-3.5 text-blue-600 shrink-0" />
                    <span className="truncate flex-1">{d.filename}</span>
                    {chatHistory[d.id]?.length > 0 && (
                      <Badge variant="secondary" className="text-xs shrink-0 h-4 px-1">
                        {chatHistory[d.id].filter((m) => m.role === "user").length}
                      </Badge>
                    )}
                  </button>
                ))
              )}
            </CardContent>
          </Card>

          {selectedDoc && (
            <Card className="shrink-0">
              <CardContent className="p-3 text-xs space-y-1.5">
                <p className="font-medium truncate">{selectedDoc.filename}</p>
                <p className="text-muted-foreground">
                  {messages.filter((m) => m.role === "user").length} questions asked
                </p>
                {messages.length > 0 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="w-full gap-1.5 text-xs text-muted-foreground hover:text-red-500 mt-1"
                    onClick={() => {
                      clearChatHistory(selectedDocId);
                    }}
                  >
                    <Trash2 className="h-3 w-3" /> Clear chat history
                  </Button>
                )}
              </CardContent>
            </Card>
          )}
        </motion.div>

        {/* Chat window */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
          className="lg:col-span-3 flex flex-col min-h-0">
          <Card className="flex-1 flex flex-col min-h-0">
            {!selectedDocId ? (
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center">
                  <MessageSquare className="h-14 w-14 mx-auto mb-4 text-muted-foreground/30" />
                  <p className="text-muted-foreground font-medium">Select a document to start chatting.</p>
                </div>
              </div>
            ) : (
              <>
                {/* Messages */}
                <div className="flex-1 overflow-y-auto p-4 space-y-4 chat-scroll">
                  {messages.length === 0 && (
                    <div className="text-center py-8">
                      <Bot className="h-10 w-10 mx-auto mb-3 text-muted-foreground/40" />
                      <p className="text-sm text-muted-foreground font-medium">
                        Ask anything about <span className="font-semibold">{selectedDoc?.filename}</span>
                      </p>
                      <div className="mt-4 flex flex-wrap gap-2 justify-center">
                        {[
                          "Who are the parties involved?",
                          "What are the key obligations?",
                          "What is the penalty clause?",
                          "Summarize the main terms.",
                        ].map((q) => (
                          <button
                            key={q}
                            onClick={() => { setInput(q); textareaRef.current?.focus(); }}
                            className="text-xs px-3 py-1.5 rounded-full border border-border hover:bg-muted/60 hover:border-blue-400 transition-all text-muted-foreground hover:text-foreground"
                          >
                            {q}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  <AnimatePresence initial={false}>
                    {messages.map((msg) => (
                      <motion.div
                        key={msg.id}
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        className={cn("flex gap-3", msg.role === "user" ? "justify-end" : "justify-start")}
                      >
                        {msg.role === "assistant" && (
                          <div className="h-8 w-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shrink-0 mt-1">
                            <Bot className="h-4 w-4 text-white" />
                          </div>
                        )}
                        <div className={cn("max-w-[80%] space-y-2", msg.role === "user" ? "items-end" : "items-start")}>
                          <div className={cn(
                            "rounded-2xl px-4 py-3 text-sm leading-relaxed",
                            msg.role === "user"
                              ? "bg-blue-600 text-white rounded-tr-sm"
                              : "bg-muted border border-border rounded-tl-sm"
                          )}>
                            {msg.content}
                          </div>
                          <p className="text-xs text-muted-foreground px-1">
                            {new Date(msg.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                          </p>

                          {/* Sources */}
                          {msg.sources && msg.sources.length > 0 && (
                            <button
                              onClick={() => setExpandedSources(expandedSources === msg.id ? null : msg.id)}
                              className="flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-700 px-1"
                            >
                              <Hash className="h-3 w-3" />
                              {msg.sources.length} source chunk{msg.sources.length !== 1 ? "s" : ""}
                              <ChevronDown className={cn("h-3 w-3 transition-transform", expandedSources === msg.id && "rotate-180")} />
                            </button>
                          )}

                          <AnimatePresence>
                            {expandedSources === msg.id && msg.sources && (
                              <motion.div
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: "auto" }}
                                exit={{ opacity: 0, height: 0 }}
                                className="space-y-1.5 overflow-hidden"
                              >
                                {msg.sources.map((src, si) => (
                                  <div
                                    key={si}
                                    className="text-xs p-2.5 rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800"
                                  >
                                    <div className="flex items-center gap-2 mb-1">
                                      <Badge variant="outline" className="text-xs h-4 px-1">
                                        Chunk #{src.chunk_index}
                                      </Badge>
                                      <span className="text-muted-foreground font-mono">
                                        {(src.score * 100).toFixed(0)}% match
                                      </span>
                                    </div>
                                    <p className="text-blue-800 dark:text-blue-300 leading-relaxed line-clamp-3">
                                      {src.chunk_text}
                                    </p>
                                  </div>
                                ))}
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                        {msg.role === "user" && (
                          <div className="h-8 w-8 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center shrink-0 mt-1">
                            <User className="h-4 w-4 text-blue-600" />
                          </div>
                        )}
                      </motion.div>
                    ))}
                  </AnimatePresence>

                  {loading && (
                    <div className="flex gap-3">
                      <div className="h-8 w-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shrink-0">
                        <Bot className="h-4 w-4 text-white" />
                      </div>
                      <div className="bg-muted border border-border rounded-2xl rounded-tl-sm px-4 py-3">
                        <div className="flex gap-1 items-center">
                          <span className="h-2 w-2 rounded-full bg-muted-foreground/50 animate-bounce" style={{ animationDelay: "0ms" }} />
                          <span className="h-2 w-2 rounded-full bg-muted-foreground/50 animate-bounce" style={{ animationDelay: "150ms" }} />
                          <span className="h-2 w-2 rounded-full bg-muted-foreground/50 animate-bounce" style={{ animationDelay: "300ms" }} />
                        </div>
                      </div>
                    </div>
                  )}

                  <div ref={messagesEndRef} />
                </div>

                {error && (
                  <div className="mx-4 mb-2 flex items-start gap-2 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-xs text-red-700 dark:text-red-400">
                    <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" /> {error}
                    <button onClick={() => setError(null)} className="ml-auto shrink-0">
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                )}

                {/* Input */}
                <Separator />
                <div className="p-4 flex gap-3 items-end">
                  <Textarea
                    ref={textareaRef}
                    placeholder="Ask a question about this document…"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    rows={1}
                    className="flex-1 resize-none text-sm min-h-[40px] max-h-32"
                  />
                  <Button
                    size="icon"
                    className="h-10 w-10 shrink-0"
                    disabled={!input.trim() || loading}
                    onClick={sendMessage}
                  >
                    {loading
                      ? <Loader2 className="h-4 w-4 animate-spin" />
                      : <Send className="h-4 w-4" />}
                  </Button>
                </div>
              </>
            )}
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
