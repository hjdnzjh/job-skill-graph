import React, { useState, useEffect } from 'react';
import {
  BarChart3,
  Calendar,
  Download,
  TrendingUp,
  TrendingDown,
  Info,
  Maximize2,
  Loader2
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, LineChart, Line, PieChart, Pie, Cell, CartesianGrid, Legend } from 'recharts';
import { getOverview, OverviewData } from '../../services/api';

export default function Reports() {
  const [timeRange, setTimeRange] = useState('3m');
  const [data, setData] = useState<OverviewData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getOverview().then(d => { setData(d); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  const COLORS = ['#6366f1', '#06b6d4', '#10b981', '#f59e0b', '#ef4444'];

  if (loading) return <div className="flex items-center justify-center h-64"><Loader2 className="h-8 w-8 animate-spin text-indigo-400" /></div>;
  if (!data) return <div className="text-slate-400 text-center py-12">加载失败</div>;

  const jobTrends = data.job_trends;
  const skillGrowth = data.skill_trends.filter(s => s.direction !== 'stable').slice(0, 10);
  const statusDist = data.status_distribution;
  const insights = data.insights;

  return (
    <div className="space-y-8">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-white">演化数据看板</h2>
          <p className="text-slate-500 text-sm">洞察岗位与技能的长周期演化趋势，支持辅助决策。</p>
        </div>
        <div className="flex items-center gap-2 bg-slate-900 p-1 rounded-lg border border-slate-800">
          {[
            { label: '近3个月', val: '3m' },
            { label: '近半年', val: '6m' },
            { label: '全年', val: '1y' },
          ].map(t => (
            <button
              key={t.val}
              onClick={() => setTimeRange(t.val)}
              className={`px-4 py-1.5 rounded-md text-xs font-medium transition-all ${
                timeRange === t.val ? 'bg-indigo-600 text-white shadow-lg' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Monthly Job Growth */}
        <Card className="border-slate-800 bg-slate-900/40">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg font-bold flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-indigo-400" />
              月度新增岗位数量
            </CardTitle>
            <Button variant="ghost" size="icon" className="h-8 w-8 text-slate-500"><Download className="h-4 w-4" /></Button>
          </CardHeader>
          <CardContent>
            <div className="h-[300px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={jobTrends}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                  <XAxis dataKey="month" stroke="#475569" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis stroke="#475569" fontSize={12} tickLine={false} axisLine={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '8px' }}
                  />
                  <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} barSize={30} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Skill Demand Trends */}
        <Card className="border-slate-800 bg-slate-900/40">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg font-bold flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-cyan-400" />
              各领域技能需求趋势
            </CardTitle>
            <Button variant="ghost" size="icon" className="h-8 w-8 text-slate-500"><Download className="h-4 w-4" /></Button>
          </CardHeader>
          <CardContent>
            <div className="h-[300px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={jobTrends}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                    <XAxis dataKey="month" stroke="#475569" fontSize={12} tickLine={false} axisLine={false} />
                    <YAxis stroke="#475569" fontSize={12} tickLine={false} axisLine={false} />
                    <Tooltip
                        contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '8px' }}
                    />
                    <Legend iconType="circle" wrapperStyle={{ fontSize: '12px', paddingTop: '20px' }} />
                    <Line type="monotone" dataKey="count" name="岗位数" stroke="#6366f1" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 6 }} />
                    <Line type="monotone" dataKey="total_nodes" name="图谱节点" stroke="#06b6d4" strokeWidth={2} strokeDasharray="5 5" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Job Status Distribution */}
        <Card className="border-slate-800 bg-slate-900/40">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg font-bold">岗位状态分布统计</CardTitle>
            <Button variant="ghost" size="icon" className="h-8 w-8 text-slate-500"><Maximize2 className="h-4 w-4" /></Button>
          </CardHeader>
          <CardContent className="flex flex-col md:flex-row items-center">
            <div className="h-[250px] w-full md:w-1/2">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={statusDist}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={80}
                    paddingAngle={5}
                    dataKey="value"
                  >
                    {statusDist.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '8px' }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="w-full md:w-1/2 space-y-4">
              {statusDist.map((status, i) => (
                <div key={i} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-3 h-3 rounded-full" style={{ backgroundColor: COLORS[i % COLORS.length] }}></div>
                    <span className="text-sm text-slate-300">{status.name}</span>
                  </div>
                  <span className="text-sm font-bold text-white">{status.value}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Insights Summary */}
        <Card className="border-slate-800 bg-slate-900/40">
          <CardHeader>
            <CardTitle className="text-lg font-bold flex items-center gap-2">
              <Info className="h-5 w-5 text-indigo-400" />
              AI 洞察摘要
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="p-4 bg-indigo-500/5 border border-indigo-500/10 rounded-xl">
              <div className="flex items-center gap-2 text-indigo-400 font-bold text-sm mb-2">
                <TrendingUp className="h-4 w-4" />
                高增长潜力
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                AI 提示词工程师岗位需求在过去 3 个月增长了 124%，主要驱动力来自内容创作与自动化办公领域的 LLM 落地。建议加大相关人才库储备。
              </p>
            </div>
            <div className="p-4 bg-red-500/5 border border-red-500/10 rounded-xl">
              <div className="flex items-center gap-2 text-red-400 font-bold text-sm mb-2">
                <TrendingDown className="h-4 w-4" />
                存量岗位萎缩
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                传统基础数据录入与初级运维岗位需求下降了 15%，相关从业者正在向 AIOps 与 数据治理方向转型。
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
