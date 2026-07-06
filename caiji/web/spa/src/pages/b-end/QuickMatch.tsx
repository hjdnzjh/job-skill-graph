import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Briefcase, Zap, CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { getJobTitles, postMatch } from '../../services/api';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { ScrollReveal } from '../../components/common/ScrollReveal';

export default function QuickMatch() {
  const [titles, setTitles] = useState<string[]>([]);
  const [target, setTarget] = useState('');
  const [skillsInput, setSkillsInput] = useState('');
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getJobTitles().then(d => { setTitles(d.titles); if (d.titles.length) setTarget(d.titles[0]); }).catch(() => {});
  }, []);

  const handleMatch = async () => {
    if (!target || !skillsInput.trim()) return;
    const skills = skillsInput.split(',').map(s => s.trim()).filter(Boolean);
    setLoading(true);
    try {
      const res = await postMatch({ skills, target });
      setResult(res);
    } catch { /* ignore */ }
    setLoading(false);
  };

  return (
    <div className="space-y-6">
      <ScrollReveal direction="down" className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">技能快速匹配</h2>
          <p className="text-slate-500 text-sm">输入你的技能清单，一键匹配最合适的岗位</p>
        </div>
      </ScrollReveal>

      <Card className="border-slate-800 bg-slate-900/40">
        <CardContent className="p-6 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-300">目标岗位</label>
              <select
                value={target}
                onChange={e => setTarget(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500"
              >
                {titles.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-300">技能清单（逗号分隔）</label>
              <input
                value={skillsInput}
                onChange={e => setSkillsInput(e.target.value)}
                placeholder="例如：Python, Java, MySQL, Docker"
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500"
                onKeyDown={e => e.key === 'Enter' && handleMatch()}
              />
            </div>
          </div>
          <Button onClick={handleMatch} disabled={loading || !target || !skillsInput.trim()} className="w-full">
            {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Zap className="h-4 w-4 mr-2" />}
            开始匹配
          </Button>
        </CardContent>
      </Card>

      {result && (
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="border-slate-800 bg-slate-900/40">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Briefcase className="h-5 w-5 text-indigo-400" />
                匹配结果: {result.target_title}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center gap-6">
                <div className="relative w-28 h-28 flex items-center justify-center">
                  <svg className="w-full h-full -rotate-90">
                    <circle cx="56" cy="56" r="48" fill="none" stroke="#1e293b" strokeWidth="8" />
                    <motion.circle
                      cx="56" cy="56" r="48" fill="none" stroke="#6366f1" strokeWidth="8" strokeLinecap="round"
                      initial={{ strokeDasharray: "0 301" }}
                      animate={{ strokeDasharray: `${result.match_score * 301} 301` }}
                      transition={{ duration: 1.5, ease: "easeOut" }}
                    />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-2xl font-bold text-white">{Math.round(result.match_score * 100)}%</span>
                  </div>
                </div>
                <div className="flex-1 space-y-2">
                  <p className="text-sm text-slate-400">匹配 {result.matched_skills?.length || 0}/{result.total_required || 0} 项核心技能</p>
                  <div className="flex flex-wrap gap-2">
                    {(result.matched_skills || []).map((s: string) => (
                      <Badge key={s} className="bg-emerald-500/10 text-emerald-400 border-emerald-500/20">
                        <CheckCircle2 className="h-3 w-3 mr-1" />{s}
                      </Badge>
                    ))}
                    {(result.missing_skills || []).map((s: string) => (
                      <Badge key={s} variant="destructive">
                        <XCircle className="h-3 w-3 mr-1" />{s}
                      </Badge>
                    ))}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}
    </div>
  );
}
