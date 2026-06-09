import React, { useEffect, useRef, useState } from 'react';
import { motion, useScroll, useTransform } from 'framer-motion';
import { Link } from 'react-router-dom';
import { Network, Briefcase, FileText, TrendingUp, ArrowRight } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardContent } from '../../components/ui/card';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip } from 'recharts';
import { getOverview, OverviewData } from '../../services/api';
import { ScrollReveal, StaggerContainer, StaggerItem } from '../../components/common/ScrollReveal';
import { CountUp } from '../../components/common/CountUp';
import { ParticleBackground } from '../../components/common/ParticleBackground';
import { GlowingText } from '../../components/common/GlowingText';
import { MagneticButton } from '../../components/common/MagneticButton';

export default function Home() {
  const { scrollY } = useScroll();
  const y1 = useTransform(scrollY, [0, 500], [0, 200]);
  const [overview, setOverview] = useState<OverviewData | null>(null);

  useEffect(() => {
    getOverview().then(setOverview).catch(() => {});
  }, []);

  const jobTrends = overview?.job_trends || [];
  const totalJobs = overview?.status_distribution?.find(d => d.name.includes('活跃'))?.value || 1188;
  const skillCount = overview?.skill_trends?.length || 128;
  const totalNodes = jobTrends[jobTrends.length - 1]?.total_nodes || 2479;

  const features = [
    {
      title: '发现新岗位',
      desc: 'AI 实时挖掘新兴职业，捕捉行业最前沿的岗位变动。',
      icon: Briefcase,
      path: '/new-jobs',
      color: 'from-blue-500 to-cyan-500',
      glow: 'group-hover:shadow-blue-500/20'
    },
    {
      title: '查看技能图谱',
      desc: '全领域技能关联图谱，清晰展现岗位能力演进路径。',
      icon: Network,
      path: '/skill-graph',
      color: 'from-purple-500 to-indigo-500',
      glow: 'group-hover:shadow-indigo-500/20'
    },
    {
      title: '简历一键测岗',
      desc: '上传简历，AI 自动分析你与未来岗位的匹配度与差距。',
      icon: FileText,
      path: '/resume-evaluate',
      color: 'from-emerald-500 to-teal-500',
      glow: 'group-hover:shadow-emerald-500/20'
    }
  ];

  return (
    <div className="flex flex-col">
      {/* Hero Section */}
      <section className="relative h-[85vh] flex items-center justify-center overflow-hidden">
        <div className="absolute inset-0 z-0">
          <motion.div style={{ y: y1 }} className="absolute inset-0">
            <ParticleBackground />
            <div className="absolute inset-0 bg-gradient-to-b from-indigo-500/10 via-transparent to-[#0a0e17]"></div>
          </motion.div>
        </div>

        <div className="container relative z-10 mx-auto px-4 text-center">
          <ScrollReveal direction="up" duration={0.8}>
            <h1 className="text-5xl md:text-7xl font-extrabold text-white mb-6 tracking-tight">
              <ScrollReveal direction="up" delay={0.1}>
                洞见未来岗位
              </ScrollReveal>
              <div className="mt-2">
                <GlowingText className="pb-2">
                  智配人才新生态
                </GlowingText>
              </div>
            </h1>
            <ScrollReveal direction="up" delay={0.3}>
              <p className="text-xl text-slate-400 mb-10 max-w-2xl mx-auto leading-relaxed">
                基于 AI 的全球岗位演化图谱，助你精准定位技能坐标，在瞬息万变的技术浪潮中抢占先机。
              </p>
            </ScrollReveal>
            
            <ScrollReveal direction="up" delay={0.5}>
              <div className="flex flex-wrap items-center justify-center gap-6">
                <MagneticButton>
                  <Link to="/skill-graph">
                    <Button size="lg" className="relative h-14 px-10 text-lg rounded-full bg-indigo-600 hover:bg-indigo-500 shadow-[0_0_30px_rgba(99,102,241,0.4)] group overflow-hidden">
                      <span className="relative z-10">开始探索</span>
                      <motion.div 
                        className="absolute inset-0 bg-white/20 translate-y-full group-hover:translate-y-0 transition-transform duration-300"
                      />
                      <div className="absolute -inset-1 bg-white/20 blur-xl opacity-0 group-hover:opacity-100 transition-opacity rounded-full pulse-ring" />
                    </Button>
                  </Link>
                </MagneticButton>
                
                <MagneticButton>
                  <Link to="/new-jobs">
                    <Button variant="outline" size="lg" className="h-14 px-10 text-lg rounded-full border-slate-700 hover:border-indigo-500 hover:bg-indigo-500/5 transition-all">
                      了解更多
                    </Button>
                  </Link>
                </MagneticButton>
              </div>
            </ScrollReveal>
          </ScrollReveal>
        </div>
      </section>

      {/* Feature Cards */}
      <section className="container mx-auto px-4 -mt-24 relative z-20 pb-20">
        <StaggerContainer stagger={0.2} className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {features.map((f, i) => (
            <StaggerItem key={i} direction="up">
              <Link to={f.path}>
                <Card className={`bg-slate-900/50 border-slate-800 backdrop-blur-xl group hover:-translate-y-2 hover:shadow-2xl ${f.glow} transition-all duration-500 overflow-hidden`}>
                  <CardContent className="p-8">
                    <div className={`w-14 h-14 rounded-2xl bg-gradient-to-br ${f.color} flex items-center justify-center mb-6 shadow-lg group-hover:scale-110 transition-transform duration-500`}>
                      <f.icon className="h-7 w-7 text-white" />
                    </div>
                    <h3 className="text-xl font-bold text-white mb-3 group-hover:text-indigo-400 transition-colors">{f.title}</h3>
                    <p className="text-slate-400 leading-relaxed mb-6">{f.desc}</p>
                    <div className="flex items-center text-indigo-400 font-medium group-hover:gap-2 transition-all">
                      立即前往 <ArrowRight className="ml-2 h-4 w-4" />
                    </div>
                  </CardContent>
                  {/* Decorative corner glow */}
                  <div className={`absolute -right-10 -bottom-10 w-32 h-32 bg-gradient-to-br ${f.color} opacity-0 group-hover:opacity-10 blur-3xl transition-opacity duration-500`} />
                </Card>
              </Link>
            </StaggerItem>
          ))}
        </StaggerContainer>
      </section>

      {/* Stats/Trends Section */}
      <section className="py-24 relative overflow-hidden">
        <div className="container mx-auto px-4 relative z-10">
          <ScrollReveal direction="up" className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">全球岗位需求趋势</h2>
            <p className="text-slate-400">实时追踪 500+ 核心技术岗位的市场需求波动</p>
          </ScrollReveal>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-12 items-center">
            <div className="lg:col-span-2">
              <ScrollReveal direction="left" delay={0.2} className="bg-slate-900/40 border border-slate-800 p-8 rounded-3xl backdrop-blur-sm">
                <div className="h-[400px] w-full" style={{ minWidth: '300px', width: '100%' }}>
                  <ResponsiveContainer width="100%" height={400} minWidth={300}>
                    <AreaChart data={jobTrends}>
                      <defs>
                        <linearGradient id="colorTrend" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <XAxis dataKey="month" stroke="#475569" fontSize={12} tickLine={false} axisLine={false} />
                      <YAxis stroke="#475569" fontSize={12} tickLine={false} axisLine={false} />
                      <Tooltip
                        contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '12px' }}
                        itemStyle={{ color: '#818cf8' }}
                      />
                      <Area
                        type="monotone"
                        dataKey="count"
                        stroke="#6366f1"
                        strokeWidth={3}
                        fillOpacity={1}
                        fill="url(#colorTrend)"
                        animationDuration={2000}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </ScrollReveal>
            </div>

            <StaggerContainer stagger={0.2} className="space-y-6">
              {[
                { label: '收录岗位总数', value: totalJobs, suffix: '+', icon: Briefcase },
                { label: '技能图谱节点', value: skillCount, suffix: '+', icon: Network },
                { label: '图谱总节点', value: totalNodes, suffix: '+', icon: TrendingUp },
              ].map((stat, i) => (
                <StaggerItem key={i} direction="right">
                  <div className="bg-slate-900/40 border border-slate-800 p-6 rounded-2xl flex items-center gap-6 hover:bg-slate-800/50 transition-colors group">
                    <div className="w-12 h-12 rounded-xl bg-indigo-500/10 flex items-center justify-center text-indigo-400 group-hover:scale-110 transition-transform">
                      <stat.icon className="h-6 w-6" />
                    </div>
                    <div>
                      <div className="text-slate-400 text-sm mb-1">{stat.label}</div>
                      <div className="text-3xl font-bold text-white">
                        <CountUp to={stat.value} suffix={stat.suffix} />
                      </div>
                    </div>
                  </div>
                </StaggerItem>
              ))}
            </StaggerContainer>
          </div>
        </div>
        
        {/* Background glow */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-indigo-600/5 blur-[120px] rounded-full -z-10" />
      </section>
    </div>
  );
}
