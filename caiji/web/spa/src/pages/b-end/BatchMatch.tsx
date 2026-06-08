import React, { useState } from 'react';
import { 
  Users, 
  Upload, 
  Play, 
  FileText, 
  Download, 
  Search,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  AlertCircle,
  RefreshCw
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { mockJobs } from '../../lib/mockData';

export default function BatchMatch() {
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const [selectedJobId, setSelectedJobId] = useState(mockJobs[0].id);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const candidates = [
    { id: 1, name: '张三', score: 92, matchSkills: ['Python', 'NLP', 'PyTorch'], gapSkills: ['提示词工程'] },
    { id: 2, name: '李四', score: 78, matchSkills: ['Python', 'Docker'], gapSkills: ['NLP', 'Hadoop'] },
    { id: 3, name: '王五', score: 65, matchSkills: ['SQL', 'React'], gapSkills: ['Python', 'NLP'] },
    { id: 4, name: '赵六', score: 88, matchSkills: ['Python', 'NLP', 'TensorFlow'], gapSkills: ['LLM 微调'] },
  ];

  const handleStartAnalysis = () => {
    setIsAnalyzing(true);
    setTimeout(() => {
      setIsAnalyzing(false);
      setShowResults(true);
    }, 2500);
  };

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-white">批量简历匹配</h2>
        <p className="text-slate-500 text-sm">一键分析整批简历与特定岗位的契合度，快速筛选候选人。</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Upload & Config */}
        <Card className="lg:col-span-1 border-slate-800 bg-slate-900/40">
          <CardHeader>
            <CardTitle className="text-lg">匹配配置</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-4">
              <label className="text-sm font-medium text-slate-300">目标招聘岗位</label>
              <select 
                value={selectedJobId}
                onChange={(e) => setSelectedJobId(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2 text-sm text-slate-200"
              >
                {mockJobs.map(j => <option key={j.id} value={j.id}>{j.name}</option>)}
              </select>
            </div>

            <div className="space-y-4">
              <label className="text-sm font-medium text-slate-300">上传简历文件夹</label>
              <div className="border-2 border-dashed border-slate-800 rounded-xl p-8 flex flex-col items-center justify-center text-center hover:border-indigo-500/50 transition-colors cursor-pointer group">
                <Upload className="h-8 w-8 text-slate-500 mb-4 group-hover:text-indigo-400" />
                <span className="text-xs text-slate-400">支持多文件选择 (PDF/Word)</span>
                <input type="file" multiple className="hidden" />
              </div>
            </div>

            <Button 
              className="w-full h-12" 
              disabled={isAnalyzing}
              onClick={handleStartAnalysis}
            >
              {isAnalyzing ? (
                <span className="flex items-center gap-2">
                  <RefreshCw className="h-5 w-5 animate-spin" />
                  深度分析中...
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <Play className="h-5 w-5" /> 一键批量匹配
                </span>
              )}
            </Button>
          </CardContent>
        </Card>

        {/* Results Area */}
        <Card className="lg:col-span-2 border-slate-800 bg-slate-900/40 min-h-[500px]">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg">匹配结果列表</CardTitle>
            {showResults && <Button variant="outline" size="sm" className="border-slate-700"><Download className="h-4 w-4 mr-2" /> 导出报表</Button>}
          </CardHeader>
          <CardContent>
            {!showResults ? (
              <div className="h-full flex flex-col items-center justify-center py-20 text-slate-600">
                <Users className="h-16 w-16 mb-4 opacity-20" />
                <p>暂无数据，请先上传简历并开始分析</p>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center gap-4 pb-4 border-b border-slate-800">
                  <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
                    <Input placeholder="搜索候选人..." className="pl-10 h-9 bg-slate-950 border-slate-800" />
                  </div>
                  <Badge variant="outline" className="border-slate-700">共 4 位候选人</Badge>
                </div>

                <div className="divide-y divide-slate-800">
                  {candidates.sort((a,b) => b.score - a.score).map((c) => (
                    <div key={c.id} className="py-4">
                      <div 
                        className="flex items-center justify-between cursor-pointer group"
                        onClick={() => setExpandedId(expandedId === c.id ? null : c.id)}
                      >
                        <div className="flex items-center gap-4">
                          <div className="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center font-bold text-slate-400 group-hover:bg-indigo-600 group-hover:text-white transition-colors">
                            {c.name[0]}
                          </div>
                          <div>
                            <div className="text-sm font-bold text-white">{c.name}</div>
                            <div className="text-[10px] text-slate-500">匹配技能: {c.matchSkills.length} | 缺失: {c.gapSkills.length}</div>
                          </div>
                        </div>
                        <div className="flex items-center gap-8">
                          <div className="w-48 h-2 bg-slate-800 rounded-full overflow-hidden hidden md:block">
                            <motion.div 
                              initial={{ width: 0 }}
                              animate={{ width: `${c.score}%` }}
                              className={`h-full ${c.score >= 80 ? 'bg-emerald-500' : 'bg-amber-500'}`}
                            />
                          </div>
                          <div className={`text-sm font-bold w-12 text-right ${c.score >= 80 ? 'text-emerald-400' : 'text-amber-400'}`}>
                            {c.score}%
                          </div>
                          {expandedId === c.id ? <ChevronUp className="h-4 w-4 text-slate-500" /> : <ChevronDown className="h-4 w-4 text-slate-500" />}
                        </div>
                      </div>

                      <AnimatePresence>
                        {expandedId === c.id && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            className="overflow-hidden"
                          >
                            <div className="mt-4 p-4 bg-slate-950/50 rounded-lg border border-slate-800 grid grid-cols-2 gap-6">
                              <div>
                                <h5 className="text-[10px] font-bold text-slate-500 uppercase mb-2 flex items-center gap-1">
                                  <CheckCircle2 className="h-3 w-3 text-emerald-500" /> 匹配技能
                                </h5>
                                <div className="flex flex-wrap gap-1.5">
                                  {c.matchSkills.map(s => <Badge key={s} variant="outline" className="text-[10px] py-0 border-emerald-500/20 text-emerald-400">{s}</Badge>)}
                                </div>
                              </div>
                              <div>
                                <h5 className="text-[10px] font-bold text-slate-500 uppercase mb-2 flex items-center gap-1">
                                  <AlertCircle className="h-3 w-3 text-red-500" /> 缺失技能
                                </h5>
                                <div className="flex flex-wrap gap-1.5">
                                  {c.gapSkills.map(s => <Badge key={s} variant="outline" className="text-[10px] py-0 border-red-500/20 text-red-400">{s}</Badge>)}
                                </div>
                              </div>
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
