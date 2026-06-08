import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { User, Star, FileText, History, Settings, LogOut, ChevronRight, Briefcase } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../../components/ui/tabs';
import { mockJobs } from '../../lib/mockData';

export default function Profile() {
  const [activeTab, setActiveTab] = useState('favorites');

  const stats = [
    { label: '已收藏岗位', value: 12, icon: Star, color: 'text-yellow-500' },
    { label: '测评报告', value: 8, icon: FileText, color: 'text-indigo-500' },
    { label: '匹配记录', value: 24, icon: History, color: 'text-emerald-500' },
  ];

  return (
    <div className="container mx-auto px-4 py-12 max-w-6xl">
      {/* Profile Header */}
      <div className="flex flex-col md:flex-row items-center gap-8 mb-12 bg-slate-900/40 p-8 rounded-3xl border border-slate-800">
        <div className="relative">
          <div className="w-32 h-32 rounded-full bg-slate-800 border-4 border-indigo-500/20 flex items-center justify-center overflow-hidden">
            <User className="h-16 w-16 text-slate-600" />
          </div>
          <button className="absolute bottom-1 right-1 p-2 bg-indigo-600 rounded-full text-white shadow-lg">
            <Settings className="h-4 w-4" />
          </button>
        </div>
        <div className="flex-1 text-center md:text-left">
          <h1 className="text-3xl font-bold text-white mb-2">智岗探索者</h1>
          <p className="text-slate-400 mb-6">求职目标: AI 提示词工程师 / 大数据架构师</p>
          <div className="flex flex-wrap justify-center md:justify-start gap-4">
            <Button size="sm" variant="outline" className="border-slate-700">编辑资料</Button>
            <Button size="sm" variant="ghost" className="text-red-400 hover:bg-red-400/10">退出登录</Button>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-8 px-8 border-l border-slate-800 hidden lg:grid">
          {stats.map((s, i) => (
            <div key={i} className="text-center">
              <div className={`flex justify-center mb-2 ${s.color}`}><s.icon className="h-5 w-5" /></div>
              <div className="text-2xl font-bold text-white">{s.value}</div>
              <div className="text-[10px] text-slate-500 uppercase tracking-wider">{s.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Tabs Content */}
      <Tabs className="w-full">
        <TabsList className="bg-slate-900/50 border border-slate-800 mb-8">
          <TabsTrigger 
            active={activeTab === 'favorites'} 
            onClick={() => setActiveTab('favorites')}
            className="px-8"
          >
            已收藏岗位
          </TabsTrigger>
          <TabsTrigger 
            active={activeTab === 'reports'} 
            onClick={() => setActiveTab('reports')}
            className="px-8"
          >
            历史测评报告
          </TabsTrigger>
          <TabsTrigger 
            active={activeTab === 'history'} 
            onClick={() => setActiveTab('history')}
            className="px-8"
          >
            过往匹配记录
          </TabsTrigger>
        </TabsList>

        <TabsContent active={activeTab === 'favorites'}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {mockJobs.slice(0, 4).map((job) => (
              <Card key={job.id} className="bg-slate-900/40 border-slate-800 hover:border-indigo-500/30 transition-all group">
                <CardContent className="p-6">
                  <div className="flex justify-between items-start mb-4">
                    <div className="flex gap-4">
                      <div className="w-12 h-12 rounded-xl bg-slate-800 flex items-center justify-center">
                        <Briefcase className="h-6 w-6 text-indigo-400" />
                      </div>
                      <div>
                        <h3 className="font-bold text-white group-hover:text-indigo-400 transition-colors">{job.name}</h3>
                        <p className="text-xs text-slate-500">{job.category} · 2025-05-20</p>
                      </div>
                    </div>
                    <Button variant="ghost" size="icon" className="text-yellow-500"><Star className="h-4 w-4 fill-current" /></Button>
                  </div>
                  <div className="flex gap-2 mb-6">
                    {job.requiredSkills.slice(0, 3).map(s => (
                      <Badge key={s} variant="outline" className="text-[10px]">{s}</Badge>
                    ))}
                  </div>
                  <div className="flex gap-3">
                    <Button size="sm" className="flex-1">投递简历</Button>
                    <Button size="sm" variant="outline" className="flex-1">查看详情</Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent active={activeTab === 'reports'}>
          <Card className="bg-slate-900/40 border-slate-800">
            <CardContent className="p-0">
              <div className="divide-y divide-slate-800">
                {[
                  { job: 'AI 提示词工程师', score: 85, date: '2025-05-28' },
                  { job: '大数据架构师', score: 72, date: '2025-05-24' },
                  { job: '智能系统运维', score: 64, date: '2025-05-15' },
                ].map((report, i) => (
                  <div key={i} className="p-6 flex items-center justify-between hover:bg-slate-800/20 transition-colors group">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-lg bg-indigo-500/10 flex items-center justify-center text-indigo-400">
                        <FileText className="h-5 w-5" />
                      </div>
                      <div>
                        <h4 className="font-bold text-white">{report.job}</h4>
                        <p className="text-xs text-slate-500">测评日期: {report.date}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-8">
                      <div className="text-right">
                        <div className={`text-xl font-bold ${report.score >= 80 ? 'text-emerald-400' : 'text-amber-400'}`}>{report.score}</div>
                        <div className="text-[10px] text-slate-500 uppercase">匹配得分</div>
                      </div>
                      <Button variant="ghost" size="sm" className="group-hover:text-indigo-400">查看详情 <ChevronRight className="ml-1 h-4 w-4" /></Button>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent active={activeTab === 'history'}>
          <div className="bg-slate-900/40 rounded-xl border border-slate-800 p-12 text-center">
            <History className="h-12 w-12 text-slate-700 mx-auto mb-4" />
            <h3 className="text-lg font-bold text-white mb-2">暂无更多匹配记录</h3>
            <p className="text-slate-500 text-sm">快去新兴岗位专区寻找感兴趣的职位吧！</p>
            <Button className="mt-6">探索岗位</Button>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
