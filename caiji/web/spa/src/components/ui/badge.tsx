import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "../../lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-indigo-600 text-white hover:bg-indigo-700",
        secondary:
          "border-transparent bg-slate-800 text-slate-100 hover:bg-slate-700",
        destructive:
          "border-transparent bg-red-500/10 text-red-500 border-red-500/20",
        outline: "text-slate-100 border-slate-700",
        success: "border-transparent bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
        warning: "border-transparent bg-amber-500/10 text-amber-500 border-amber-500/20",
        cyan: "border-transparent bg-cyan-500/10 text-cyan-500 border-cyan-500/20",
        purple: "border-transparent bg-purple-500/10 text-purple-500 border-purple-500/20",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
