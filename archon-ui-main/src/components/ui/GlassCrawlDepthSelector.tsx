import React from 'react';
import { motion } from 'framer-motion';
import { NeonButton } from './NeonButton';
import { cn } from '../../lib/utils';

interface GlassCrawlDepthSelectorProps {
  value: number;
  onChange: (value: number) => void;
  showTooltip?: boolean;
  onTooltipToggle?: (show: boolean) => void;
  className?: string;
}

export const GlassCrawlDepthSelector: React.FC<GlassCrawlDepthSelectorProps> = ({
  value,
  onChange,
  showTooltip = false,
  onTooltipToggle,
  className
}) => {
  const levels = [1, 2, 3, 4, 5];
  
  // Get descriptive text for each level
  const getLevelDescription = (level: number) => {
    switch (level) {
      case 1: return "Single page only";
      case 2: return "Immediate links";
      case 3: return "2 levels deep";
      case 4: return "3 levels deep";
      case 5: return "Maximum depth";
      default: return "";
    }
  };

  const getLevelColor = (level: number) => {
    if (level <= value) return 'blue';
    return 'none';
  };

  return (
    <div className={cn("relative", className)}>
      {/* Main container for circles and tubes */}
      <div className="flex items-center justify-between gap-0 relative">
        {/* Glass tubes connecting the circles */}
        {levels.slice(0, -1).map((level, index) => (
          <motion.div
            key={`tube-${level}`}
            className={cn(
              "absolute h-2 transition-all duration-500",
              "backdrop-blur-md rounded-full overflow-hidden",
              level < value 
                ? "bg-gradient-to-r from-blue-500/20 to-blue-400/20 border border-blue-400/30" 
                : "bg-white/5 dark:bg-white/5 border border-white/10"
            )}
            style={{
              left: `${(index * 25) + 12.5}%`,
              width: "25%",
              top: "50%",
              transform: "translateY(-50%)",
              zIndex: 0
            }}
            initial={{ scaleX: 0 }}
            animate={{ scaleX: 1 }}
            transition={{ delay: index * 0.1, duration: 0.3 }}
          >
            {/* Animated glow inside tube when active */}
            {level < value && (
              <motion.div
                className="absolute inset-0 bg-gradient-to-r from-transparent via-blue-400/50 to-transparent"
                animate={{
                  x: ["-100%", "200%"]
                }}
                transition={{
                  duration: 2,
                  repeat: Infinity,
                  ease: "linear",
                  delay: index * 0.2
                }}
              />
            )}
          </motion.div>
        ))}
        
        {/* Glass circle buttons */}
        {levels.map((level) => {
          const isSelected = level <= value;
          const isActive = level === value;
          
          return (
            <motion.div
              key={level}
              className="relative z-10"
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.95 }}
            >
              <div className="relative">
                {/* Red glow behind unselected circles */}
                {!isSelected && (
                  <motion.div
                    className="absolute inset-0 rounded-full bg-red-500/20 blur-xl"
                    animate={{
                      scale: [1, 1.2, 1],
                      opacity: [0.3, 0.5, 0.3]
                    }}
                    transition={{
                      duration: 3,
                      repeat: Infinity,
                      ease: "easeInOut"
                    }}
                  />
                )}
                
                <NeonButton
                  onClick={() => onChange(level)}
                  size="lg"
                  className="relative w-16 h-16 p-0 rounded-full overflow-visible"
                  showLayer2={true}
                  layer2Inset={6}
                  layer1Color="none"
                  layer2Color={isSelected ? 'blue' : 'none'}
                  layer1Radius={{ topLeft: 32, topRight: 32, bottomRight: 32, bottomLeft: 32 }}
                  layer2Radius={{ topLeft: 28, topRight: 28, bottomRight: 28, bottomLeft: 28 }}
                  layer1Glow="none"
                  layer2Glow={isSelected ? 'xl' : 'none'}
                  borderGlow={isSelected ? 'lg' : 'none'}
                  layer1Border={false}
                  layer2Border={true}
                  coloredText={false}
                >
                  {/* Glass background effect - Layer 1 */}
                  <div className={cn(
                    "absolute inset-0 rounded-full transition-all duration-500",
                    "bg-black/95 dark:bg-black/95",
                    "backdrop-blur-xl",
                    !isSelected && "border border-red-500/30"
                  )} />
                  
                  {/* Inner glass layer for number */}
                  <div className={cn(
                    "absolute inset-[6px] rounded-full transition-all duration-500",
                    "backdrop-blur-md",
                    isSelected 
                      ? "bg-gradient-to-b from-blue-500/20 to-blue-600/30 border border-blue-400/50" 
                      : "bg-gradient-to-b from-white/5 to-white/10 border border-white/20"
                  )}>
                    {/* Blue glow effect when selected */}
                    {isSelected && (
                      <motion.div
                        className="absolute inset-0 rounded-full"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ duration: 0.5 }}
                      >
                        <div className="absolute inset-0 rounded-full bg-blue-500/30 blur-md" />
                      </motion.div>
                    )}
                  </div>
                  
                  {/* Number display */}
                  <span className={cn(
                    "relative z-20 text-2xl font-bold transition-all duration-500",
                    isSelected 
                      ? "text-blue-300 drop-shadow-[0_0_15px_rgba(59,130,246,1)]" 
                      : "text-gray-400/60 dark:text-gray-500/60"
                  )}>
                    {level}
                  </span>
                </NeonButton>
                
                {/* Active pulse animation */}
                {isActive && (
                  <motion.div
                    className="absolute inset-0 rounded-full"
                    initial={{ scale: 1, opacity: 0 }}
                    animate={{ 
                      scale: [1, 1.5, 1], 
                      opacity: [0, 0.3, 0] 
                    }}
                    transition={{
                      duration: 2,
                      repeat: Infinity,
                      ease: "easeOut"
                    }}
                  >
                    <div className="w-full h-full rounded-full bg-blue-500" />
                  </motion.div>
                )}
              </div>
              
              {/* Level description on hover */}
              <motion.div
                className={cn(
                  "absolute -bottom-8 left-1/2 transform -translate-x-1/2",
                  "text-xs whitespace-nowrap transition-opacity duration-300",
                  "pointer-events-none"
                )}
                initial={{ opacity: 0 }}
                whileHover={{ opacity: 1 }}
              >
                <span className={cn(
                  "px-2 py-1 rounded-md backdrop-blur-sm",
                  "bg-black/70 text-white/80",
                  "shadow-lg"
                )}>
                  {getLevelDescription(level)}
                </span>
              </motion.div>
            </motion.div>
          );
        })}
      </div>
      
      {/* Selected level indicator text */}
      <div className="mt-12 text-center">
        <div className="text-sm text-gray-600 dark:text-zinc-400">
          {value === 1 && "Single page or sitemap entries only"}
          {value === 2 && "Recommended - includes immediate links"}
          {value === 3 && "Deep - follows links 2 levels deep"}
          {value === 4 && "Very deep - 3 levels of link following"}
          {value === 5 && "Maximum depth - comprehensive crawling"}
        </div>
      </div>
      
      {/* Detailed tooltip */}
      {showTooltip && onTooltipToggle && (
        <motion.div 
          className="absolute z-50 bottom-full left-0 mb-4 p-4 bg-gray-900 dark:bg-black text-white rounded-lg shadow-xl w-full max-w-md backdrop-blur-md border border-gray-700"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 10 }}
        >
          <h4 className="font-semibold mb-2">Crawl Depth Explained</h4>
          <div className="space-y-2 text-sm">
            <div className={cn("transition-all duration-300", value === 1 ? "text-blue-300" : "")}>
              <span className="font-medium text-blue-400">Level 1:</span> Only the URL you provide (1-50 pages)
              <div className="text-gray-400 text-xs">Best for: Single articles, specific pages</div>
            </div>
            <div className={cn("transition-all duration-300", value === 2 ? "text-green-300" : "")}>
              <span className="font-medium text-green-400">Level 2:</span> URL + all linked pages (10-200 pages)
              <div className="text-gray-400 text-xs">Best for: Documentation sections, blogs</div>
            </div>
            <div className={cn("transition-all duration-300", value === 3 ? "text-yellow-300" : "")}>
              <span className="font-medium text-yellow-400">Level 3:</span> URL + 2 levels of links (50-500 pages)
              <div className="text-gray-400 text-xs">Best for: Entire sites, comprehensive docs</div>
            </div>
            <div className={cn("transition-all duration-300", value >= 4 ? "text-orange-300" : "")}>
              <span className="font-medium text-orange-400">Level 4-5:</span> Very deep crawling (100-1000+ pages)
              <div className="text-gray-400 text-xs">Warning: May include irrelevant content</div>
            </div>
          </div>
          <div className="mt-3 pt-3 border-t border-gray-700 text-xs text-gray-400">
            💡 More data isn't always better. Choose based on your needs.
          </div>
        </motion.div>
      )}
    </div>
  );
};