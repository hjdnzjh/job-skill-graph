import React, { useState, useEffect } from 'react';
import {
  Settings2,
  Search,
  ArrowRight,
  Plus,
  Minus,
  RefreshCw,
  Download,
  Filter,
  Eye,
  CheckCircle,
  Loader2,
  X
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { Drawer } from '../../components/common/Drawer';
import { TaxonomyTree, TaxonomyNode } from '../../components/common/TaxonomyTree';
import { getSkillTree } from '../../services/api';

async function fetchSkillChanges() {
  const res = await fetch('/api/skills/changes');
  if (!res.ok) return [];
  const d = await res.json();
  return d.changes || [];
}

export default function SkillManage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [selectedRecord, setSelectedRecord] = useState<any>(null);
  const [changeRecords, setChangeRecords] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterOpen, setFilterOpen] = useState(false);
  const [selectedDomains, setSelectedDomains] = useState<string[]>([]);
  const [taxonomyData, setTaxonomyData] = useState<TaxonomyNode[]>([]);

  useEffect(() => {
    fetchSkillChanges().then(d => { setChangeRecords(d); setLoading(false); }).catch(() => setLoading(false));
    getSkillTree().then(d => setTaxonomyData(d.tree || [])).catch(() => {});
  }, []);

  const filteredRecords = changeRecords.filter(r => {
    if (selectedDomains.length === 0) return true;
    return selectedDomains.some(code =>
      r.domain_code === code || r.domain === code
    );
  });

  const handleOpenDetail = (record: any) => {
    setSelectedRecord(record);
    setIsDetailOpen(true);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-white">存量岗位能力管理</h2>
          <p className="text-slate-500 text-sm">监控并确认已有岗位的技能要求变更，保持图谱时效性。</p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" className="border-slate-700">
            <Download className="mr-2 h-4 w-4" /> 导出技能清单
          </Button>
          <Button size="sm">
            <RefreshCw className="mr-2 h-4 w-4" /> 触发全局扫描
          </Button>
        </div>
      </div>

      <Card className="border-slate-800 bg-slate-900/40">
        <CardHeader className="flex flex-row items-center justify-between pb-6">
          <div className="relative w-72">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
            <Input 
              placeholder="搜索岗位变更..." 
              className="pl-10"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-2 relative">
            <Button
              variant="ghost"
              size="sm"
              className={`text-slate-400 ${selectedDomains.length > 0 ? 'text-indigo-400 bg-indigo-500/10' : ''}`}
              onClick={() => setFilterOpen(!filterOpen)}
            >
              <Filter className="h-4 w-4 mr-2" />
              筛选{selectedDomains.length > 0 ? ` (${selectedDomains.length})` : ''}
            </Button>
            {filterOpen && (
              <div className="absolute right-0 top-full mt-2 z-50 w-80 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl p-4">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-sm font-bold text-white">按领域筛选</h4>
                  <button onClick={() => setFilterOpen(false)} className="text-slate-500 hover:text-white">
                    <X className="h-4 w-4" />
                  </button>
                </div>
                <TaxonomyTree
                  data={taxonomyData}
                  value={selectedDomains}
                  onChange={setSelectedDomains}
                  multiple={true}
                  searchable={true}
                  placeholder="搜索领域..."
                />
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-slate-800 text-slate-500 text-xs uppercase tracking-wider">
                  <th className="px-6 py-4 font-semibold">岗位名称</th>
                  <th className="px-6 py-4 font-semibold">变更类型</th>
                  <th className="px-6 py-4 font-semibold">具体变更内容</th>
                  <th className="px-6 py-4 font-semibold">发现时间</th>
                  <th className="px-6 py-4 font-semibold text-right">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {filteredRecords.map((record) => (
                  <tr key={record.id} className="hover:bg-slate-800/30 transition-colors group">
                    <td className="px-6 py-4 text-sm font-medium text-white">{record.title}</td>
                    <td className="px-6 py-4">
                      {record.change_type === 'add' && <Badge variant="success" className="bg-emerald-500/10 text-emerald-400 border-emerald-500/20">新增技能</Badge>}
                      {record.change_type === 'modify' && <Badge variant="warning" className="bg-amber-500/10 text-amber-400 border-amber-500/20">修改技能</Badge>}
                      {record.change_type === 'remove' && <Badge variant="destructive" className="bg-red-500/10 text-red-500 border-red-500/20">删除技能</Badge>}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2 text-sm text-slate-300">
                        {record.change_type === 'add' && <Plus className="h-3 w-3 text-emerald-500" />}
                        {record.change_type === 'remove' && <Minus className="h-3 w-3 text-red-500" />}
                        {record.skill}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-500">{record.date}</td>
                    <td className="px-6 py-4 text-right">
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className="text-indigo-400 hover:text-indigo-300 p-0"
                        onClick={() => handleOpenDetail(record)}
                      >
                        <Eye className="h-4 w-4 mr-1" /> 详情
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Detail Drawer */}
      <Drawer
        isOpen={isDetailOpen}
        onClose={() => setIsDetailOpen(false)}
        title="岗位能力变更详情"
      >
        {selectedRecord && (
          <div className="space-y-8">
            <div className="p-4 bg-slate-800/50 rounded-xl border border-slate-700">
              <div className="text-xs text-slate-500 uppercase mb-1">目标岗位</div>
              <div className="text-lg font-bold text-white">{selectedRecord.title}</div>
            </div>

            <div className="space-y-4">
              <h4 className="text-sm font-semibold text-slate-300 border-b border-slate-800 pb-2">变更对比</h4>
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 bg-slate-950/50 rounded-lg border border-slate-800">
                  <div className="text-[10px] text-slate-500 uppercase mb-2">变更前</div>
                  <div className="text-sm text-slate-400 line-through">
                    {selectedRecord.change_type === 'modify' ? 'React 基础' : selectedRecord.change_type === 'remove' ? selectedRecord.skill : '无'}
                  </div>
                </div>
                <div className="p-4 bg-indigo-500/5 rounded-lg border border-indigo-500/20">
                  <div className="text-[10px] text-indigo-400 uppercase mb-2">变更后</div>
                  <div className="text-sm text-white font-medium">
                    {selectedRecord.change_type === 'modify' ? 'Next.js 框架' : selectedRecord.change_type === 'add' ? selectedRecord.skill : '已移除'}
                  </div>
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <h4 className="text-sm font-semibold text-slate-300 border-b border-slate-800 pb-2">自动生成说明</h4>
              <p className="text-sm text-slate-400 leading-relaxed bg-slate-900 p-4 rounded-lg">
                基于 {selectedRecord.source} 的最新数据分析，该岗位在实际招聘中对 {selectedRecord.skill} 的关注度显著{selectedRecord.change_type === 'add' ? '提升' : '下降'}。建议及时同步至全量图谱。
              </p>
            </div>

            <div className="space-y-4">
              <h4 className="text-sm font-semibold text-slate-300 border-b border-slate-800 pb-2">数据来源</h4>
              <div className="flex items-center gap-2 text-sm text-indigo-400">
                <RefreshCw className="h-4 w-4" />
                {selectedRecord.source}
              </div>
            </div>

            <div className="pt-6 flex gap-3">
              <Button variant="outline" className="flex-1 border-slate-700" onClick={() => setIsDetailOpen(false)}>暂不处理</Button>
              <Button className="flex-1 bg-emerald-600 hover:bg-emerald-700">
                <CheckCircle className="mr-2 h-4 w-4" /> 确认并同步
              </Button>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}
