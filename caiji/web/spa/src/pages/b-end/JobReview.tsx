import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ClipboardCheck,
  Search,
  CheckCircle2,
  XCircle,
  Save,
  Plus,
  X,
  Info,
  Loader2
} from 'lucide-react';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { getPendingJobs, getJobDetail } from '../../services/api';
import { ScrollReveal, StaggerContainer, StaggerItem } from '../../components/common/ScrollReveal';

export default function JobReview() {
  const [jobs, setJobs] = useState<any[]>([]);
  const [selectedJob, setSelectedJob] = useState<any>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getPendingJobs({ status: 'pending', limit: 100 }).then(d => { setJobs(d.jobs); setSelectedJob(d.jobs[0] || null); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (selectedJob?.title) {
      getJobDetail(selectedJob.title).then(d => setSelectedJob((prev: any) => ({ ...prev, ...d }))).catch(() => {});
    }
  }, [selectedJob?.title]);

  const filteredJobs = jobs.filter((j: any) => j.title.toLowerCase().includes(searchTerm.toLowerCase()));

  return (
    <div className="flex gap-6 h-[calc(100vh-160px)]">
      {/* Left List */}
      <div className="w-[400px] flex flex-col gap-4">
        <ScrollReveal direction="left" className="flex-shrink-0 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
          <Input 
            placeholder="搜索待审岗位..." 
            className="pl-10 bg-slate-900 border-slate-800 focus:border-indigo-500 transition-all"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </ScrollReveal>
        
        <div className="flex-1 overflow-y-auto space-y-3 pr-2 no-scrollbar">
          <h3 className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-2 px-1">AI 自动挖掘待审核 ({filteredJobs.length})</h3>
          <StaggerContainer stagger={0.05}>
            {filteredJobs.map((job) => (
              <StaggerItem key={job.id} direction="left">
                <div
                  onClick={() => setSelectedJob(job)}
                  className={`relative p-4 rounded-xl border cursor-pointer transition-all overflow-hidden group ${
                    selectedJob.id === job.id 
                      ? 'bg-indigo-600/10 border-indigo-500/50 shadow-lg shadow-indigo-500/10' 
                      : 'bg-slate-900 border-slate-800 hover:border-slate-700 hover:bg-slate-800/50'
                  }`}
                >
                  {/* Hover border slide effect */}
                  <motion.div 
                    initial={{ x: '-100%' }}
                    whileHover={{ x: '0%' }}
                    className="absolute left-0 top-0 bottom-0 w-1 bg-indigo-500"
                  />
                  
                  <div className="flex justify-between items-start mb-2 relative z-10">
                    <h4 className={`font-bold text-sm transition-colors ${selectedJob?.title === job.title ? 'text-indigo-400' : 'text-white'}`}>{job.title}</h4>
                    <Badge variant={job.status === 'pending' ? 'warning' : 'success'} className="text-[10px]">
                      {job.status === 'pending' ? '待审核' : '已挖掘'}
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between text-[10px] text-slate-500 relative z-10">
                    <span>领域: {job.category}</span>
                    <span>{job.date}</span>
                  </div>
                </div>
              </StaggerItem>
            ))}
          </StaggerContainer>
        </div>
      </div>

      {/* Right Edit Panel */}
      <div className="flex-1">
        <AnimatePresence mode="wait">
          <motion.div
            key={selectedJob.title}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="h-full"
          >
            <Card className="h-full border-slate-800 bg-slate-900/40 flex flex-col backdrop-blur-sm">
              <div className="p-6 border-b border-slate-800 flex items-center justify-between flex-shrink-0">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 rounded-lg bg-indigo-500/20 text-indigo-400 flex items-center justify-center shadow-[0_0_15px_rgba(99,102,241,0.2)]">
                    <ClipboardCheck className="h-6 w-6" />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-white">岗位审核与编辑</h3>
                    <p className="text-xs text-slate-500">正在审核: {selectedJob.title}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Button variant="outline" size="sm" className="border-slate-700 hover:bg-slate-800">
                    <Save className="mr-2 h-4 w-4" /> 暂存编辑
                  </Button>
                  <Button variant="destructive" size="sm" className="bg-red-500/10 text-red-400 border-red-500/20 hover:bg-red-500/20">
                    <XCircle className="mr-2 h-4 w-4" /> 驳回归档
                  </Button>
                  <Button size="sm" className="bg-emerald-600 hover:bg-emerald-500 shadow-[0_0_15px_rgba(16,185,129,0.3)]">
                    <CheckCircle2 className="mr-2 h-4 w-4" /> 通过上架
                  </Button>
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-8 no-scrollbar">
                <div className="max-w-3xl mx-auto space-y-8">
                  {/* Form Fields */}
                  <div className="grid grid-cols-2 gap-6">
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-slate-300">岗位名称</label>
                      <Input defaultValue={selectedJob.title} className="bg-slate-950 border-slate-800 focus:border-indigo-500" />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-slate-300">行业分类</label>
                      <Input defaultValue={selectedJob.category || selectedJob.industries?.[0] || ''} className="bg-slate-950 border-slate-800 focus:border-indigo-500" />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium text-slate-300">岗位描述</label>
                    <textarea
                      className="w-full min-h-[120px] bg-slate-950 border border-slate-800 rounded-lg p-3 text-sm text-slate-300 focus:outline-none focus:border-indigo-500"
                      defaultValue={selectedJob.description || selectedJob.responsibilities || ''}
                    />
                  </div>

                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <label className="text-sm font-medium text-slate-300">核心技能标签 ({(selectedJob.required_skills || selectedJob.requiredSkills || []).length})</label>
                      <Button variant="ghost" size="sm" className="h-7 text-xs text-indigo-400 hover:text-indigo-300">
                        <Plus className="mr-1 h-3 w-3" /> 添加技能
                      </Button>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {[...(selectedJob.required_skills || selectedJob.requiredSkills || [])].map((skill: any, i: number) => {
                        const name = typeof skill === 'string' ? skill : skill.name || skill.skill || '';
                        return (
                        <Badge key={i} className="bg-slate-800 text-slate-300 border-slate-700 py-1 pl-3 pr-1 flex items-center gap-1 group">
                          {name}
                          <button className="p-0.5 rounded-full hover:bg-slate-700 opacity-0 group-hover:opacity-100 transition-opacity">
                            <X className="h-3 w-3" />
                          </button>
                        </Badge>
                      );})}
                    </div>
                  </div>

                  <div className="p-4 rounded-xl bg-indigo-500/5 border border-indigo-500/10 flex items-start gap-3">
                    <Info className="h-5 w-5 text-indigo-400 mt-0.5" />
                    <div className="text-xs text-slate-400 leading-relaxed">
                      <p className="text-indigo-400 font-bold mb-1">AI 审核建议:</p>
                      该岗位描述完整度 95%，技能标签匹配度高。建议在“岗位描述”中增加 2-3 个具体的业务应用场景描述以提升吸引力。
                    </div>
                  </div>
                </div>
              </div>
            </Card>
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
