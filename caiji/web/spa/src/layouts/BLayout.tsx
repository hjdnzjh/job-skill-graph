import React from 'react';
import { Link, useLocation, Outlet } from 'react-router-dom';
import {
  LayoutDashboard,
  ClipboardCheck,
  Settings2,
  Network,
  Users,
  BarChart3,
  LogOut,
  Bell,
  Search,
  Zap
} from 'lucide-react';
import { cn } from '../lib/utils';
import { Button } from '../components/ui/button';
import { motion, AnimatePresence } from 'framer-motion';
import { ProgressBar } from '../components/common/ProgressBar';

export default function BLayout() {
  const location = useLocation();

  const menuItems = [
    { name: '数据工作台', path: '/admin', icon: LayoutDashboard },
    { name: '新岗位审核', path: '/admin/job-review', icon: ClipboardCheck },
    { name: '存量岗位管理', path: '/admin/skill-manage', icon: Settings2 },
    { name: '图谱管理', path: '/admin/graph-manage', icon: Network },
    { name: '技能匹配', path: '/admin/quick-match', icon: Zap },
    { name: '批量简历匹配', path: '/admin/batch-resume', icon: Users },
    { name: '数据报表', path: '/admin/reports', icon: BarChart3 },
  ];

  const currentTitle = menuItems.find(item => item.path === location.pathname)?.name || '后台管理';

  return (
    <div className="flex h-screen bg-[#0a0e17] text-slate-100 overflow-hidden">
      <ProgressBar />
      
      {/* Sidebar */}
      <aside className="w-64 flex-shrink-0 border-r border-slate-800 bg-slate-950 flex flex-col z-20">
        <div className="p-6">
          <Link to="/" className="flex items-center gap-2 group">
            <motion.div 
              whileHover={{ rotate: 180 }}
              className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 shadow-[0_0_15px_rgba(99,102,241,0.4)]"
            >
              <Network className="h-5 w-5 text-white" />
            </motion.div>
            <span className="text-xl font-bold tracking-tight text-white group-hover:text-indigo-400 transition-colors">智岗后台</span>
          </Link>
        </div>

        <nav className="flex-1 px-4 space-y-1 overflow-y-auto no-scrollbar">
          {menuItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={cn(
                "relative flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all group overflow-hidden",
                location.pathname === item.path
                  ? "text-indigo-400"
                  : "text-slate-400 hover:text-slate-100"
              )}
            >
              {/* Background slide animation */}
              {location.pathname === item.path && (
                <motion.div 
                  layoutId="sidebar-active"
                  className="absolute inset-0 bg-indigo-600/10 border border-indigo-500/20 rounded-lg -z-10"
                />
              )}
              
              {/* Left active bar */}
              {location.pathname === item.path && (
                <motion.div 
                  layoutId="sidebar-bar"
                  className="absolute left-0 top-2 bottom-2 w-1 bg-indigo-500 rounded-full shadow-[0_0_10px_rgba(99,102,241,0.8)]"
                />
              )}

              <item.icon className={cn(
                "h-5 w-5 transition-colors",
                location.pathname === item.path ? "text-indigo-400" : "text-slate-500 group-hover:text-slate-300"
              )} />
              <span className="relative z-10">{item.name}</span>
            </Link>
          ))}
        </nav>

        <div className="p-4 border-t border-slate-800">
          <Link to="/">
            <motion.div whileHover={{ x: -4 }} transition={{ type: "spring", stiffness: 400, damping: 10 }}>
              <Button variant="ghost" className="w-full justify-start text-slate-400 hover:text-red-400 hover:bg-red-400/10">
                <LogOut className="mr-2 h-4 w-4" />
                退出后台
              </Button>
            </motion.div>
          </Link>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
        {/* Topbar */}
        <header className="h-16 flex-shrink-0 border-b border-slate-800 bg-slate-950/50 backdrop-blur-md flex items-center justify-between px-8 z-10">
          <motion.h1 
            key={currentTitle}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            className="text-lg font-semibold text-white"
          >
            {currentTitle}
          </motion.h1>
          
          <div className="flex items-center gap-6">
            <div className="relative hidden md:block group">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500 group-focus-within:text-indigo-400 transition-colors" />
              <input 
                type="text" 
                placeholder="搜索岗位/简历..." 
                className="bg-slate-900 border border-slate-800 rounded-full pl-10 pr-4 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50 w-64 transition-all"
              />
            </div>
            <button className="relative p-2 text-slate-400 hover:text-white transition-colors">
              <Bell className="h-5 w-5" />
              <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full border-2 border-slate-950"></span>
            </button>
            <div className="flex items-center gap-3 pl-4 border-l border-slate-800">
              <div className="text-right hidden sm:block text-[10px]">
                <div className="text-sm font-medium text-white">管理员</div>
                <div className="text-slate-500">超级管理员</div>
              </div>
              <motion.div 
                whileHover={{ scale: 1.1 }}
                className="h-9 w-9 rounded-full bg-slate-800 flex items-center justify-center border border-slate-700 overflow-hidden"
              >
                <img src="https://modao.cc/agent-py/media/generated_images/2026-06-03/9c2b2122512f41469b41dd909fdb190d.jpg#desc=Admin" alt="Admin" className="w-full h-full object-cover" />
              </motion.div>
            </div>
          </div>
        </header>

        {/* Scrollable Area with Transitions */}
        <main className="flex-1 overflow-y-auto overflow-x-hidden no-scrollbar bg-[#0a0e17]">
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.3 }}
              className="p-8"
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}
