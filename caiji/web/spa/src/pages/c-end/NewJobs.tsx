import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Flame, ChevronDown, ChevronUp, Star, MapPin, Clock, Briefcase, ArrowRight, Loader2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { Card, CardContent } from '../../components/ui/card';
import { getPendingJobs, getJobTree, TaxonomyNode } from '../../services/api';
import { ScrollReveal, StaggerContainer, StaggerItem } from '../../components/common/ScrollReveal';

export default function NewJobs() {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('全部');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [favorites, setFavorites] = useState<string[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [domains, setDomains] = useState<TaxonomyNode[]>([]);

  useEffect(() => {
    // Fetch job taxonomy for domain tabs
    getJobTree().then(d => setDomains(d.tree || [])).catch(() => {});
    // Fetch pending jobs
    getPendingJobs({ limit: 100 }).then(d => {
      const mapped = d.jobs.map((j: any, i: number) => ({
        ...j,
        id: `job_${i}`,
        title: j.title,
        name: j.title,
        duties: j.description || j.responsibilities || '暂无描述',
        category: j.category || '新兴岗位',
        domain_code: j.domain_code || '',
        domain_name: j.domain_name || '',
        requiredSkills: (j.required_skills || []).map((s: any) => typeof s === 'string' ? s : s.name || s.skill || ''),
        heat: Math.round((j.confidence || 0.5) * 100),
        date: j.date || '',
      }));
      setJobs(mapped); setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const filteredJobs = jobs.filter((job: any) => {
    const matchesSearch = job.title.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory = selectedCategory === '全部' ||
      job.category === selectedCategory ||
      job.domain_name === selectedCategory ||
      job.domain_code === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  const toggleFavorite = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    setFavorites(prev => 
      prev.includes(id) ? prev.filter(fid => fid !== id) : [...prev, id]
    );
  };

  return (
    <div className="container mx-auto px-4 py-12">
      <ScrollReveal direction="down" className="flex flex-col md:flex-row md:items-center justify-between gap-6 mb-12">
        <div>
          <h1 className="text-4xl font-bold text-white mb-2">新兴岗位专区</h1>
          <p className="text-slate-400">洞察未来职场动态，发现属于你的下一个机会。</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative group">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500 group-focus-within:text-indigo-400 transition-colors" />
            <Input 
              placeholder="搜索岗位名称..." 
              className="pl-10 w-64 bg-slate-900 border-slate-800 focus:border-indigo-500 transition-all"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <div className="flex bg-slate-900 p-1 rounded-lg border border-slate-800">
            <button
              onClick={() => setSelectedCategory('全部')}
              className={`relative px-4 py-1.5 rounded-md text-sm font-medium transition-all overflow-hidden ${
                selectedCategory === '全部' ? 'text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {selectedCategory === '全部' && (
                <motion.div
                  layoutId="cat-active"
                  className="absolute inset-0 bg-indigo-600 shadow-lg"
                />
              )}
              <span className="relative z-10">全部</span>
            </button>
            {domains.map(d => (
              <button
                key={d.code}
                onClick={() => setSelectedCategory(d.name)}
                className={`relative px-4 py-1.5 rounded-md text-sm font-medium transition-all overflow-hidden ${
                  selectedCategory === d.name ? 'text-white' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {selectedCategory === d.name && (
                  <motion.div
                    layoutId="cat-active"
                    className="absolute inset-0 bg-indigo-600 shadow-lg"
                  />
                )}
                <span className="relative z-10">{d.name}</span>
              </button>
            ))}
          </div>
        </div>
      </ScrollReveal>

      <StaggerContainer stagger={0.1} className="grid grid-cols-1 gap-6">
        {filteredJobs.map((job) => (
          <StaggerItem key={job.id} direction="up">
            <Card 
              className={`overflow-hidden transition-all duration-500 border-slate-800 hover:border-indigo-500/50 ${
                expandedId === job.id ? 'ring-1 ring-indigo-500/50 bg-slate-900/80 shadow-2xl' : 'bg-slate-900/40'
              } group`}
            >
              <div 
                className="p-6 cursor-pointer flex flex-col md:flex-row md:items-center justify-between gap-6"
                onClick={() => toggleExpand(job.id)}
              >
                <div className="flex items-start gap-4">
                  <motion.div 
                    whileHover={{ scale: 1.1, rotate: 5 }}
                    className="w-12 h-12 rounded-xl bg-slate-800 flex items-center justify-center flex-shrink-0 group-hover:bg-indigo-500/20 group-hover:text-indigo-400 transition-colors"
                  >
                    <Briefcase className="h-6 w-6 text-indigo-400" />
                  </motion.div>
                  <div>
                    <div className="flex items-center gap-3 mb-1">
                      <h3 className="text-xl font-bold text-white group-hover:text-indigo-400 transition-colors">{job.title}</h3>
                      <Badge className="bg-cyan-500/10 text-cyan-400 border-cyan-500/20 text-[10px]">{job.category}</Badge>
                    </div>
                    <div className="flex items-center gap-4 text-sm text-slate-500">
                      <span className="flex items-center gap-1"><MapPin className="h-3 w-3" /> 远程/不限</span>
                      <span className="flex items-center gap-1"><Clock className="h-3 w-3" /> {job.date}</span>
                      <span className="flex items-center gap-1 text-orange-400/80">
                        <Flame className="h-3 w-3 fill-orange-400/20" /> 热度 {job.heat}%
                      </span>
                    </div>
                  </div>
                </div>
                
                <div className="flex items-center gap-4">
                  <button 
                    onClick={(e) => toggleFavorite(e, job.id)}
                    className={`p-2 rounded-full transition-all ${
                      favorites.includes(job.id) ? 'text-yellow-500 bg-yellow-500/10' : 'text-slate-500 hover:text-white hover:bg-slate-800'
                    }`}
                  >
                    <Star className={`h-5 w-5 ${favorites.includes(job.id) ? 'fill-yellow-500' : ''}`} />
                  </button>
                  <Button variant="ghost" size="sm" className="hidden md:flex gap-2">
                    {expandedId === job.id ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                    详情
                  </Button>
                </div>
              </div>

              <AnimatePresence>
                {expandedId === job.id && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.3, ease: "easeInOut" }}
                  >
                    <CardContent className="px-6 pb-6 pt-0 border-t border-slate-800/50 mt-4">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 pt-6">
                        <div className="space-y-4">
                          <h4 className="font-bold text-white flex items-center gap-2">
                            <span className="w-1 h-4 bg-indigo-500 rounded-full" />
                            岗位描述
                          </h4>
                          <p className="text-sm text-slate-400 leading-relaxed">
                            {job.duties}
                          </p>
                          <div className="flex gap-4">
                            <Link to="/resume-evaluate" className="flex-1">
                              <Button className="w-full bg-indigo-600 hover:bg-indigo-500 gap-2">
                                简历对标 <ArrowRight className="h-4 w-4" />
                              </Button>
                            </Link>
                            <Button variant="outline" className="border-slate-700">查看详情</Button>
                          </div>
                        </div>
                        <div className="space-y-4">
                          <h4 className="font-bold text-white flex items-center gap-2">
                            <span className="w-1 h-4 bg-cyan-500 rounded-full" />
                            核心技能
                          </h4>
                          <div className="flex flex-wrap gap-2">
                            {(job.requiredSkills || job.required_skills || []).map((skill: string, i: number) => (
                              <Badge key={i} variant="secondary" className="bg-slate-800 hover:bg-slate-700 transition-colors">
                                {skill}
                              </Badge>
                            ))}
                          </div>
                          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                            <div className="flex items-center justify-between text-xs text-slate-500 mb-2">
                              <span>技能匹配度参考</span>
                              <span className="text-indigo-400 font-bold">85%</span>
                            </div>
                            <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                              <motion.div 
                                initial={{ width: 0 }}
                                animate={{ width: "85%" }}
                                transition={{ duration: 1, delay: 0.3 }}
                                className="h-full bg-gradient-to-r from-indigo-500 to-cyan-400"
                              />
                            </div>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </motion.div>
                )}
              </AnimatePresence>
            </Card>
          </StaggerItem>
        ))}
      </StaggerContainer>
    </div>
  );
}
