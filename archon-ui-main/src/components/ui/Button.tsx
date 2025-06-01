import React from 'react';
/**
 * Props for the Button component
 */
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode;
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  accentColor?: 'purple' | 'green' | 'pink' | 'blue';
  neonLine?: boolean;
}
/**
 * Button - A customizable button component
 *
 * This component provides a reusable button with various styles,
 * sizes, and color options.
 */
export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  accentColor = 'purple',
  neonLine = false,
  className = '',
  ...props
}) => {
  // Style variations based on variant
  const variantClasses = {
    primary: `backdrop-blur-[2px] text-white font-medium ${accentColor === 'purple' ? 'bg-gradient-to-r from-purple-500/95 to-pink-500/95 hover:from-purple-500 hover:to-pink-500' : accentColor === 'green' ? 'bg-gradient-to-r from-emerald-500/95 to-blue-500/95 hover:from-emerald-500 hover:to-blue-500' : accentColor === 'pink' ? 'bg-gradient-to-r from-pink-500/95 to-purple-500/95 hover:from-pink-500 hover:to-purple-500' : 'bg-gradient-to-r from-blue-500/95 to-emerald-500/95 hover:from-blue-500 hover:to-emerald-500'} shadow-sm border border-white/10`,
    secondary: `backdrop-blur-[2px] bg-black/90 border text-white ${accentColor === 'purple' ? 'border-purple-500 text-purple-500' : accentColor === 'green' ? 'border-emerald-500 text-emerald-500' : accentColor === 'pink' ? 'border-pink-500 text-pink-500' : 'border-blue-500 text-blue-500'}`,
    outline: `bg-transparent border text-gray-800 dark:text-white ${accentColor === 'purple' ? 'border-purple-500/50 hover:border-purple-500 hover:bg-purple-500/5' : accentColor === 'green' ? 'border-emerald-500/50 hover:border-emerald-500 hover:bg-emerald-500/5' : accentColor === 'pink' ? 'border-pink-500/50 hover:border-pink-500 hover:bg-pink-500/5' : 'border-blue-500/50 hover:border-blue-500 hover:bg-blue-500/5'}`,
    ghost: 'bg-transparent text-gray-700 dark:text-white hover:bg-gray-100/50 dark:hover:bg-white/5'
  };
  // Size variations
  const sizeClasses = {
    sm: 'text-xs px-3 py-1.5 rounded',
    md: 'text-sm px-4 py-2 rounded-md',
    lg: 'text-base px-6 py-2.5 rounded-md'
  };
  // Neon line color mapping
  const neonLineColor = {
    purple: 'bg-purple-500 shadow-[0_0_10px_2px_rgba(168,85,247,0.4)] dark:shadow-[0_0_20px_5px_rgba(168,85,247,0.7)]',
    green: 'bg-emerald-500 shadow-[0_0_10px_2px_rgba(16,185,129,0.4)] dark:shadow-[0_0_20px_5px_rgba(16,185,129,0.7)]',
    pink: 'bg-pink-500 shadow-[0_0_10px_2px_rgba(236,72,153,0.4)] dark:shadow-[0_0_20px_5px_rgba(236,72,153,0.7)]',
    blue: 'bg-blue-500 shadow-[0_0_10px_2px_rgba(59,130,246,0.4)] dark:shadow-[0_0_20px_5px_rgba(59,130,246,0.7)]'
  };
  return <button className={`
        relative inline-flex items-center justify-center transition-all duration-200
        ${variantClasses[variant]}
        ${sizeClasses[size]}
        ${className}
      `} {...props}>
      {/* Subtle shine effect for primary buttons */}
      {variant === 'primary' && <div className="absolute inset-0 rounded-md overflow-hidden">
          <div className="absolute top-0 left-0 right-0 h-[1px] bg-white/40"></div>
          <div className="absolute bottom-0 left-0 right-0 h-[1px] bg-black/20"></div>
        </div>}
      <span className="relative z-10">{children}</span>
      {/* Optional neon line below button */}
      {neonLine && <span className={`absolute bottom-0 left-[15%] right-[15%] w-[70%] mx-auto h-[2px] ${neonLineColor[accentColor]}`}></span>}
    </button>;
};