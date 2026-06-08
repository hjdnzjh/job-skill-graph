import React, { useEffect, useState } from 'react';
import {
  ClipboardCheck,
  Settings2,
  Users,
  TrendingUp,
  ArrowUpRight,
  ArrowDownRight,
  Clock,
  Loader2
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import { getOverview, getPendingJobs, OverviewData } from '../../services/api';
import { Badge } from '../../components/ui/badge';
import { motion } from 'framer-motion';
import { CountUp } from '../../components/common/CountUp';
import { ScrollReveal, StaggerContainer, StaggerItem } from '../../components/common/ScrollReveal';

export default function Dashboard() {
  const [data, setData] = useState<OverviewData | null>(null);
  const [pendingCount, setPendingCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getOverview(),
      getPendingJobs({ status: 'pending', limit: 1 }).catch(() => ({ total: 0 })),
    ]).then(([overview, pending]) => {
      setData(overview);
      setPendingCount((pending as any).total || 0);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const stats = [
    { title: '待审核岗位', value: pendingCount, change: pendingCount > 0 ? `+${pendingCount}` : '0', trend: pendingCount > 0 ? 'up' : 'down', icon: ClipboardCheck, color: 'text-indigo-400', bg: 'bg-indigo-400/10' },
    { title: '活跃岗位', value: data?.status_distribution?.find(d => d.name === '活跃岗位')?.value || 0, change: '-', trend: 'up', icon: Settings2, color: 'text-cyan-400', bg: 'bg-cyan-400/10' },
    { title: '已归档', value: data?.status_distribution?.find(d => d.name === '已归档')?.value || 0, change: '-', trend: 'down', icon: Users, color: 'text-emerald-400', bg: 'bg-emerald-400/10' },
    { title: '技能总数', value: data?.skill_trends?.length || 0, change: '-', trend: 'up', icon: TrendingUp, color: 'text-purple-400', bg: 'bg-purple-400/10' },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-indigo-400" />
      </div>
    );
  }

  const jobTrends = data?.job_trends || [];
  const skillGrowth = (data?.skill_trends || []).slice(0, 5).map(s => ({
    name: s.name,
    value: Math.abs(s.growth),
  }));

  return (
    <div className="space-y-8">
      <ScrollReveal direction="down" className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">欢迎回来，管理员</h2>
          <p className="text-slate-500 text-sm mt-1">知识图谱数据概览</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-400 bg-slate-900 px-4 py-2 rounded-lg border border-slate-800">
          <Clock className="h-4 w-4" />
          实时数据
        </div>
      </ScrollReveal>

      {/* Stats Grid */}
      <StaggerContainer stagger={0.1} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat, i) => (
          <StaggerItem key={i} direction="up">
            <Card className="border-slate-800 bg-slate-900/40 hover:border-indigo-500/50 hover:bg-slate-900/60 transition-all duration-300 group">
              <CardContent className="p-6">
                <div className="flex justify-between items-start mb-4">
                  <motion.div
                    whileHover={{ rotate: 15, scale: 1.1 }}
                    className={`p-3 rounded-xl ${stat.bg} ${stat.color} transition-colors group-hover:bg-indigo-500/20`}
                  >
                    <stat.icon className="h-6 w-6" />
                  </motion.div>
                  <div className={`flex items-center gap-1 text-xs font-medium ${stat.trend === 'up' ? 'text-emerald-400' : 'text-red-400'}`}>
                    {stat.change}
                    {stat.trend === 'up' ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
                  </div>
                </div>
                <div className="text-3xl font-bold text-white tabular-nums">
                  <CountUp to={stat.value} />
                </div>
                <div className="text-sm text-slate-500 mt-1">{stat.title}</div>
              </CardContent>
            </Card>
          </StaggerItem>
        ))}
      </StaggerContainer>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <Card className="lg:col-span-8 border-slate-800 bg-slate-900/40 overflow-hidden">
          <ScrollReveal direction="left" duration={0.8} distance={20} className="h-full">
            <CardHeader className="flex flex-row items-center justify-between pb-8">
              <CardTitle className="text-lg font-bold">岗位数量趋势</CardTitle>
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="text-[10px] border-slate-700">快照数据</Badge>
              </div>
            </CardHeader>
            <CardContent>
              <div className="h-[300px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={jobTrends}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                    <XAxis dataKey="month" stroke="#475569" fontSize={12} tickLine={false} axisLine={false} />
                    <YAxis stroke="#475569" fontSize={12} tickLine={false} axisLine={false} />
                    <Tooltip
                      cursor={{ fill: '#1e293b' }}
                      contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '8px' }}
                    />
                    <Bar
                      dataKey="count"
                      fill="#6366f1"
                      radius={[4, 4, 0, 0]}
                      barSize={40}
                      animationDuration={1500}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </ScrollReveal>
        </Card>

        <Card className="lg:col-span-4 border-slate-800 bg-slate-900/40">
          <ScrollReveal direction="right" duration={0.8} distance={20} className="h-full">
            <CardHeader>
              <CardTitle className="text-lg font-bold">技能增长排行</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {skillGrowth.map((skill, i) => (
                  <div key={i} className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-300">{skill.name}</span>
                      <span className="text-white font-medium">{skill.value}%</span>
                    </div>
                    <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        whileInView={{ width: `${Math.min(skill.value, 100)}%` }}
                        transition={{ duration: 1.5, ease: "easeOut", delay: i * 0.1 }}
                        className="h-full bg-gradient-to-r from-indigo-500 to-cyan-400"
                      />
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </ScrollReveal>
        </Card>
      </div>
    </div>
  );
}
