import React from 'react';
import { Link, useLocation, Outlet } from 'react-router-dom';
import { Globe, Briefcase, Network, FileText, User, MessageSquare } from 'lucide-react';
import { Button } from '../components/ui/button';
import { motion, AnimatePresence } from 'framer-motion';
import { ProgressBar } from '../components/common/ProgressBar';

export default function CLayout() {
  const location = useLocation();
  const [isAiOpen, setIsAiOpen] = React.useState(false);

  const navItems = [
    { name: '首页', path: '/', icon: Globe },
    { name: '新兴岗位', path: '/new-jobs', icon: Briefcase },
    { name: '岗位图谱', path: '/skill-graph', icon: Network },
    { name: '简历测评', path: '/resume-evaluate', icon: FileText },
  ];

  return (
    <div className="min-h-screen bg-[#0a0e17] text-slate-100 font-sans selection:bg-indigo-500/30">
      <ProgressBar />
      
      {/* Header */}
      <header className="sticky top-0 z-40 w-full border-b border-slate-800 bg-[#0a0e17]/80 backdrop-blur-md">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          <Link to="/" className="flex items-center gap-2 group">
            <motion.div 
              whileHover={{ rotate: 180 }}
              transition={{ duration: 0.5 }}
              className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 shadow-[0_0_15px_rgba(99,102,241,0.5)]"
            >
              <Network className="h-5 w-5 text-white" />
            </motion.div>
            <span className="text-xl font-bold tracking-tight text-white group-hover:text-indigo-400 transition-colors">智岗星球</span>
          </Link>

          <nav className="hidden md:flex items-center gap-8">
            {navItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                className={`relative text-sm font-medium transition-colors py-1 group ${
                  location.pathname === item.path ? 'text-indigo-400' : 'text-slate-400 hover:text-indigo-400'
                }`}
              >
                {item.name}
                {/* Hover underline animation */}
                <motion.span 
                  className="absolute bottom-0 left-0 w-full h-0.5 bg-indigo-500 origin-center"
                  initial={{ scaleX: 0 }}
                  whileHover={{ scaleX: 1 }}
                  animate={{ scaleX: location.pathname === item.path ? 1 : 0 }}
                  transition={{ duration: 0.3 }}
                />
                {/* Active glow */}
                {location.pathname === item.path && (
                  <motion.span 
                    layoutId="nav-glow"
                    className="absolute -bottom-1 left-0 w-full h-4 bg-indigo-500/20 blur-lg -z-10"
                  />
                )}
              </Link>
            ))}
          </nav>

          <div className="flex items-center gap-4">
            <Link to="/profile">
              <motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}>
                <Button variant="ghost" size="icon" className="rounded-full">
                  <User className="h-5 w-5" />
                </Button>
              </motion.div>
            </Link>
            <Link to="/admin">
              <motion.div 
                whileHover={{ scale: 1.05 }} 
                whileTap={{ scale: 0.95 }}
              >
                <Button variant="outline" size="sm" className="hidden sm:flex border-indigo-500/50 hover:border-indigo-500 hover:bg-indigo-500/10">
                  进入后台
                </Button>
              </motion.div>
            </Link>
          </div>
        </div>
      </header>

      {/* Main Content with Page Transition */}
      <main className="relative overflow-x-hidden">
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
          >
            <Outlet />
          </motion.div>
        </AnimatePresence>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800 bg-slate-950 py-12">
        <div className="container mx-auto px-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            <div className="col-span-1 md:col-span-2">
              <div className="flex items-center gap-2 mb-4">
                <Network className="h-6 w-6 text-indigo-500" />
                <span className="text-lg font-bold text-white">智岗星球 Smart Job Planet</span>
              </div>
              <p className="text-slate-400 max-w-sm">
                利用 AI 与大数据洞察未来岗位趋势，为新时代人才提供全方位的职业进化图谱与精准对标服务。
              </p>
            </div>
            <div>
              <h4 className="text-white font-semibold mb-4">快速链接</h4>
              <ul className="space-y-2 text-sm text-slate-400">
                <li><Link to="/new-jobs" className="hover:text-indigo-400 transition-colors">新兴岗位</Link></li>
                <li><Link to="/skill-graph" className="hover:text-indigo-400 transition-colors">岗位图谱</Link></li>
                <li><Link to="/resume-evaluate" className="hover:text-indigo-400 transition-colors">简历测评</Link></li>
              </ul>
            </div>
            <div>
              <h4 className="text-white font-semibold mb-4">联系我们</h4>
              <ul className="space-y-2 text-sm text-slate-400">
                <li>邮箱: contact@jobplanet.ai</li>
                <li>数据来源: 行业公开报告 & AI 挖掘</li>
              </ul>
            </div>
          </div>
          <div className="mt-12 pt-8 border-t border-slate-900 text-center text-xs text-slate-500">
            © 2025 智岗星球. All rights reserved.
          </div>
        </div>
      </footer>

      {/* AI Chat Button */}
      <div className="fixed bottom-8 right-8 z-50">
        <div className="relative">
          {/* Breathing glow */}
          <motion.div 
            animate={{ 
              scale: [1, 1.2, 1],
              opacity: [0.5, 0.8, 0.5]
            }}
            transition={{ 
              duration: 2, 
              repeat: Infinity,
              ease: "easeInOut"
            }}
            className="absolute inset-0 rounded-full bg-indigo-500 blur-xl -z-10"
          />
          
          <motion.button
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            onClick={() => setIsAiOpen(!isAiOpen)}
            className="flex h-14 w-14 items-center justify-center rounded-full bg-indigo-600 text-white shadow-[0_0_20px_rgba(99,102,241,0.6)] transition-all"
          >
            <MessageSquare className="h-6 w-6" />
          </motion.button>
        </div>

        <AnimatePresence>
          {isAiOpen && (
            <motion.div
              initial={{ opacity: 0, y: 20, scale: 0.9, filter: "blur(10px)" }}
              animate={{ opacity: 1, y: 0, scale: 1, filter: "blur(0px)" }}
              exit={{ opacity: 0, y: 20, scale: 0.9, filter: "blur(10px)" }}
              transition={{ type: "spring", damping: 20, stiffness: 300 }}
              className="absolute bottom-16 right-0 w-80 rounded-2xl border border-slate-700 bg-slate-900/90 p-4 shadow-2xl backdrop-blur-xl"
            >
              <div className="flex items-center justify-between mb-4 border-b border-slate-800 pb-2">
                <span className="font-bold text-white">AI 智能助手</span>
                <button onClick={() => setIsAiOpen(false)} className="text-slate-500 hover:text-white">×</button>
              </div>
              <div className="h-48 overflow-y-auto mb-4 text-sm text-slate-300 space-y-3 no-scrollbar">
                <div className="bg-slate-800/50 p-2 rounded-lg">你好！我是智岗星球 AI，想了解什么岗位或技能？</div>
              </div>
              <div className="flex gap-2">
                <input 
                  type="text" 
                  placeholder="输入问题..." 
                  className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-indigo-500"
                />
                <Button size="sm" className="bg-indigo-600 hover:bg-indigo-500">发送</Button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
