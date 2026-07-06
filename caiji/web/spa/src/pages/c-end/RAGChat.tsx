import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Send, Bot, User, Loader2, Sparkles } from 'lucide-react';
import { queryRag } from '../../services/api';
import { ScrollReveal } from '../../components/common/ScrollReveal';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

export default function RAGChat() {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', content: '你好！我是岗位知识图谱助手。问我关于技能、岗位、薪资的任何问题！' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSend = async () => {
    if (!input.trim() || loading) return;
    const q = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: q }]);
    setLoading(true);
    try {
      const res = await queryRag(q, 5);
      setMessages(prev => [...prev, { role: 'assistant', content: res.answer || '暂无回答' }]);
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: '抱歉，服务暂时不可用，请稍后再试。' }]);
    }
    setLoading(false);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-64px)] max-w-4xl mx-auto">
      <ScrollReveal direction="down" className="border-b border-slate-800 px-6 py-4 flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-indigo-600/20">
            <Sparkles className="h-5 w-5 text-indigo-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">智能问答</h1>
            <p className="text-xs text-slate-500">基于知识图谱的岗位技能问答</p>
          </div>
        </div>
      </ScrollReveal>

      <div className="flex-1 overflow-y-auto p-6 space-y-4 no-scrollbar">
        {messages.map((msg, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}
          >
            {msg.role === 'assistant' && (
              <div className="w-8 h-8 rounded-lg bg-indigo-600/20 flex items-center justify-center flex-shrink-0">
                <Bot className="h-4 w-4 text-indigo-400" />
              </div>
            )}
            <div className={`max-w-[75%] p-4 rounded-2xl ${
              msg.role === 'user'
                ? 'bg-indigo-600 text-white rounded-br-md'
                : 'bg-slate-900 border border-slate-800 text-slate-200 rounded-bl-md'
            }`}>
              <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
            </div>
            {msg.role === 'user' && (
              <div className="w-8 h-8 rounded-lg bg-slate-800 flex items-center justify-center flex-shrink-0">
                <User className="h-4 w-4 text-slate-400" />
              </div>
            )}
          </motion.div>
        ))}
        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-600/20 flex items-center justify-center">
              <Bot className="h-4 w-4 text-indigo-400" />
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-2xl rounded-bl-md p-4">
              <Loader2 className="h-5 w-5 animate-spin text-indigo-400" />
            </div>
          </div>
        )}
      </div>

      <div className="border-t border-slate-800 p-4 flex-shrink-0">
        <div className="flex gap-3">
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSend()}
            placeholder="例如：Java开发需要什么技能？"
            className="flex-1 bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-indigo-500"
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="px-4 py-3 bg-indigo-600 text-white rounded-xl hover:bg-indigo-500 disabled:opacity-50 transition-all"
          >
            <Send className="h-5 w-5" />
          </button>
        </div>
      </div>
    </div>
  );
}
